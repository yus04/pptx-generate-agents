from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import MSO_AUTO_SIZE
from pptx.enum.shapes import MSO_SHAPE_TYPE
import io
from typing import Dict, Any, Optional, List
import requests
import tempfile
import os
import uvicorn
import json
import uuid

from a2a.types import AgentCard, AgentSkill, DataPart, Message, TextPart, Part, Role
from a2a.server.agent_execution import AgentExecutor
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.apps import A2AStarletteApplication
from a2a.server.tasks.inmemory_task_store import InMemoryTaskStore
from a2a.server.agent_execution import RequestContext
from a2a.server.events.event_queue import EventQueue

from shared.models import SlideContent, SlideAgenda
from shared.storage import blob_client
from shared.config import settings


class SlideCreationExecutor(AgentExecutor):
    def __init__(self):
        # Azure AI Project Client を初期化
        self.ai_client = AIProjectClient(
            endpoint=settings.azure_ai_foundry_endpoint,
            credential=DefaultAzureCredential()
        )
    
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """スライド作成を実行"""
        try:
            # RequestContext から必要な情報を取得
            parts = context.message.parts
            if not parts or len(parts) == 0:
                print("✗ Error: Message parts are required")
                return
            payload_part = parts[0]
            if not isinstance(payload_part.root, DataPart):
                print("✗ Error: First part must be DataPart")
                return
            
            # payloadが既に辞書の場合と文字列の場合を処理
            raw_data = payload_part.root.data
            if isinstance(raw_data, dict):
                data_part = raw_data
            else:
                data_part = json.loads(raw_data)
            print(f"   ✓ Received data part: {data_part}")

            payload = data_part.get("payload", {})
            agenda_data = payload.get("agenda", {})
            information = payload.get("information", {})
            template_id = payload.get("template_id")
            include_images = payload.get("include_images", True)
            include_tables = payload.get("include_tables", True)
            
            if not agenda_data:
                print("✗ Error: agenda data is required")
                return
                
            agenda = SlideAgenda(**agenda_data)
            
            # 情報をもとにスライドコンテンツを生成・改善
            enhanced_agenda = await self._enhance_slide_content_with_ai(agenda, information)
            
            # スライド作成
            pptx_data = await self._create_presentation(
                enhanced_agenda, information, template_id, include_images, include_tables
            )

            # スライドコンテンツを抽出してレビュー用に準備
            slide_contents = await self._extract_slide_contents(pptx_data, enhanced_agenda)
            
            # ユーザーIDを取得（context から）
            user_id = getattr(context, 'user_id', 'default_user')
            
            # Blob Storage にアップロード
            filename = f"presentation_{enhanced_agenda.slides[0].title[:20]}.pptx"
            blob_url = blob_client.upload_bytes(
                pptx_data, filename, user_id, "presentations"
            )
            
            # 結果をEventQueueに送信
            result_json = json.dumps({
                "slide_url": blob_url, 
                "filename": filename,
                "slide_contents": slide_contents
            }, ensure_ascii=False)
            
            message = Message(
                message_id=str(uuid.uuid4()),
                role=Role.agent,
                context_id=context.message.context_id,
                parts=[Part(root=TextPart(text=result_json))]
            )
            await event_queue.enqueue_event(message)
            print(f"   ✓ Slide creation completed. File: {filename}, URL: {blob_url}")
        
        except Exception as e:
            print(f"✗ Error in slide creation: {e}")
            error_message = Message(
                message_id=str(uuid.uuid4()),
                role=Role.agent,
                context_id=context.message.context_id,
                parts=[Part(root=TextPart(text=json.dumps({"error": str(e)}, ensure_ascii=False)))]
            )
            await event_queue.enqueue_event(error_message)
    
    async def cancel(self, request_id: str) -> bool:
        """処理をキャンセル"""
        return True
    
    async def _enhance_slide_content_with_ai(
        self, 
        agenda: SlideAgenda, 
        information: Dict[str, Any]
    ) -> SlideAgenda:
        """AIを使用してスライドコンテンツを強化"""
        try:
            # スライドごとに情報を使ってコンテンツを改善
            enhanced_slides = []
            
            for slide in agenda.slides:
                slide_key = f"slide_{slide.page_number}"
                slide_info = information.get(slide_key, {})
                
                # 収集された情報をもとに、スライド用のコンテンツを生成
                enhanced_content = await self._generate_slide_content_with_ai(
                    slide.title,
                    slide.content,
                    slide_info
                )
                
                # 改善されたスライドコンテンツを作成
                # データ型の最終確認と変換
                content_value = enhanced_content.get("content", slide.content)
                if isinstance(content_value, list):
                    content_value = "\n".join(str(item) for item in content_value)
                elif not isinstance(content_value, str):
                    content_value = str(content_value)
                
                title_value = enhanced_content.get("title", slide.title)
                if not isinstance(title_value, str):
                    title_value = str(title_value)
                
                notes_value = enhanced_content.get("notes", slide.notes)
                if notes_value is not None and not isinstance(notes_value, str):
                    notes_value = str(notes_value)
                
                images_value = enhanced_content.get("images", slide.images)
                if not isinstance(images_value, list):
                    images_value = [images_value] if images_value else []
                
                tables_value = enhanced_content.get("tables", slide.tables)
                if not isinstance(tables_value, list):
                    tables_value = [tables_value] if tables_value else []
                
                enhanced_slide = SlideContent(
                    page_number=slide.page_number,
                    title=title_value,
                    content=content_value,
                    notes=notes_value,
                    images=images_value,
                    tables=tables_value
                )
                enhanced_slides.append(enhanced_slide)
            
            return SlideAgenda(
                slides=enhanced_slides,
                total_pages=len(enhanced_slides),
                estimated_duration=agenda.estimated_duration
            )
            
        except Exception as e:
            print(f"Warning: Failed to enhance content with AI: {e}")
            return agenda  # フォールバックとして元のアジェンダを返す
    
    async def _generate_slide_content_with_ai(
        self,
        title: str,
        original_content: str,
        slide_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """AIを使用して個別スライドのコンテンツを生成"""
        try:
            agents_client = self.ai_client.agents
            
            # Create agent for content generation
            agent = agents_client.create_agent(
                model=os.environ.get("MODEL_DEPLOYMENT_NAME", "gpt-4"),
                name="slide-content-generator",
                instructions="""あなたはPowerPointスライドのコンテンツ生成の専門家です。
                
                与えられた情報を基に、以下の要件でスライドのコンテンツを作成してください：
                
                1. **簡潔性**: スライドに適した簡潔でわかりやすい文章
                2. **構造化**: 箇条書きや番号付きリストを活用
                3. **視覚性**: 図表や画像で説明できる部分を特定
                4. **実用性**: 聴衆にとって有益で実用的な内容
                5. **正確性**: 提供された情報に基づく正確な内容
                
                回答は以下のJSON形式で提供してください：
                {
                  "title": "改善されたタイトル",
                  "content": "スライド用に最適化されたコンテンツ（箇条書きなど）",
                  "notes": "スピーカーノート（詳細情報や注意点）",
                  "images": ["推奨画像URL1", "推奨画像URL2"],
                  "tables": [{"headers": ["列1", "列2"], "rows": [["データ1", "データ2"]]}]
                }""",
                tools=[],
            )
            
            # Create thread for communication
            thread = agents_client.threads.create()
            
            # 情報を統合してプロンプトを作成
            collected_text = slide_info.get("text", "")
            sources = slide_info.get("sources", [])
            existing_images = slide_info.get("images", [])
            existing_tables = slide_info.get("tables", [])
            
            prompt = f"""
            以下の情報を基に、PowerPointスライド用のコンテンツを生成してください。
            
            **スライドタイトル**: {title}
            **現在のコンテンツ**: {original_content}
            
            **収集された詳細情報**:
            {collected_text[:2000] if collected_text else "追加情報なし"}
            
            **参考ソース**:
            {chr(10).join(sources[:5]) if sources else "ソースなし"}
            
            **利用可能な画像**:
            {chr(10).join(existing_images[:3]) if existing_images else "画像なし"}
            
            スライドに適した簡潔で分かりやすいコンテンツを作成し、JSON形式で返してください。
            """
            
            # Create message
            message = agents_client.messages.create(
                thread_id=thread.id,
                role="user",
                content=prompt,
            )
            
            # Create and process run
            run = agents_client.runs.create_and_process(
                thread_id=thread.id, 
                agent_id=agent.id
            )
            
            # Collect results
            enhanced_content = {
                "title": title,
                "content": original_content,
                "notes": "",
                "images": existing_images[:2],  # 最大2つの画像
                "tables": existing_tables[:1]  # 最大1つのテーブル
            }
            
            if run.status == "completed":
                # Fetch messages
                messages = agents_client.messages.list(thread_id=thread.id)
                for msg in messages:
                    if msg.role == "assistant" and msg.text_messages:
                        for text_message in msg.text_messages:
                            try:
                                # JSON レスポンスをパース
                                ai_response = json.loads(text_message.text.value)
                                
                                # データ型の検証と変換
                                if "content" in ai_response:
                                    content = ai_response["content"]
                                    if isinstance(content, list):
                                        # リストの場合は文字列に変換
                                        ai_response["content"] = "\n".join(str(item) for item in content)
                                    elif not isinstance(content, str):
                                        # その他の型の場合は文字列に変換
                                        ai_response["content"] = str(content)
                                
                                # その他のフィールドの型検証
                                if "title" in ai_response and not isinstance(ai_response["title"], str):
                                    ai_response["title"] = str(ai_response["title"])
                                
                                if "notes" in ai_response and ai_response["notes"] is not None and not isinstance(ai_response["notes"], str):
                                    ai_response["notes"] = str(ai_response["notes"])
                                
                                if "images" in ai_response and not isinstance(ai_response["images"], list):
                                    ai_response["images"] = [ai_response["images"]] if ai_response["images"] else []
                                
                                if "tables" in ai_response and not isinstance(ai_response["tables"], list):
                                    ai_response["tables"] = [ai_response["tables"]] if ai_response["tables"] else []
                                
                                enhanced_content.update(ai_response)
                                break
                            except json.JSONDecodeError:
                                # JSON パースに失敗した場合はテキストとして使用
                                enhanced_content["content"] = text_message.text.value
                                
            elif run.status == "failed":
                print(f"Content generation run failed: {run.last_error}")
            
            # Clean up
            agents_client.delete_agent(agent.id)
            
            return enhanced_content
                
        except Exception as e:
            print(f"AI content generation failed: {e}")
            return {
                "title": title,
                "content": original_content,
                "notes": "",
                "images": slide_info.get("images", [])[:2],
                "tables": slide_info.get("tables", [])[:1]
            }
    
    async def _extract_slide_contents(self, pptx_data: bytes, agenda: SlideAgenda) -> List[Dict[str, Any]]:
        """レビュー用にスライドの実際のコンテンツを抽出"""
        try:
            pptx_file = io.BytesIO(pptx_data)
            prs = Presentation(pptx_file)
            
            slide_contents = []
            for i, slide in enumerate(prs.slides):
                slide_text_parts = []
                images = []
                tables = []
                
                # テキストコンテンツを抽出
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        slide_text_parts.append(shape.text.strip())
                    
                    # 画像情報を収集
                    if shape.shape_type == 13:  # Picture
                        images.append({
                            "type": "image",
                            "description": "画像が含まれています",
                            "size": {
                                "width": int(shape.width) if hasattr(shape, 'width') else 0,
                                "height": int(shape.height) if hasattr(shape, 'height') else 0
                            }
                        })
                    
                    # テーブル情報を収集
                    if hasattr(shape, 'table'):
                        table_data = []
                        try:
                            for row in shape.table.rows:
                                row_data = [cell.text for cell in row.cells]
                                table_data.append(row_data)
                            tables.append({
                                "type": "table",
                                "data": table_data,
                                "rows": len(table_data),
                                "columns": len(table_data[0]) if table_data else 0
                            })
                        except Exception as e:
                            print(f"Error extracting table data: {e}")
                            tables.append({
                                "type": "table",
                                "data": [],
                                "error": str(e)
                            })
                
                # 対応するアジェンダ情報を取得
                agenda_slide = None
                if i < len(agenda.slides):
                    agenda_slide = agenda.slides[i]
                
                slide_content = {
                    "slide_number": i + 1,
                    "title": agenda_slide.title if agenda_slide else f"スライド {i + 1}",
                    "planned_content": agenda_slide.content if agenda_slide else "",
                    "actual_text": "\n".join(slide_text_parts),
                    "images": images,
                    "tables": tables,
                    "shape_count": len(slide.shapes),
                    "has_notes": bool(slide.notes_slide.notes_text_frame.text.strip()) if hasattr(slide, 'notes_slide') else False
                }
                slide_contents.append(slide_content)
            
            return slide_contents
            
        except Exception as e:
            print(f"Failed to extract slide contents: {e}")
            return []
    
    async def _create_presentation(
        self, 
        agenda: SlideAgenda, 
        information: Dict[str, Any],
        template_id: Optional[str],
        include_images: bool,
        include_tables: bool
    ) -> bytes:
        """PowerPoint プレゼンテーションを作成"""
        
        # テンプレートまたは新規プレゼンテーション
        if template_id:
            prs = await self._load_template(template_id)
        else:
            prs = Presentation()
        
        # 既存のスライドをクリア（テンプレートの場合）
        if template_id and len(prs.slides) > 0:
            # 最初のスライドをマスターとして保持
            slide_layouts = prs.slide_layouts
        else:
            slide_layouts = prs.slide_layouts
        
        # スライド作成
        for slide_content in agenda.slides:
            self._create_slide(
                prs, slide_content, information, 
                include_images, include_tables, slide_layouts
            )
        
        # バイナリデータとして出力
        output = io.BytesIO()
        prs.save(output)
        output.seek(0)
        return output.getvalue()
    
    async def _load_template(self, template_id: str) -> Presentation:
        """テンプレートを読み込み"""
        # Cosmos DB からテンプレート情報を取得
        from ...shared.storage import cosmos_client
        
        # 簡略化のため、直接 Presentation を作成
        # 実際の実装では template_id から Blob URL を取得してダウンロード
        return Presentation()
    
    def _create_slide(
        self, 
        prs: Presentation, 
        slide_content: SlideContent,
        information: Dict[str, Any],
        include_images: bool,
        include_tables: bool,
        slide_layouts
    ):
        """個別スライドを作成"""
        
        # スライドレイアウトを選択
        if slide_content.page_number == 1:
            # タイトルスライド
            slide_layout = slide_layouts[0]  # Title Slide
        else:
            # コンテンツスライド
            slide_layout = slide_layouts[1]  # Title and Content
        
        slide = prs.slides.add_slide(slide_layout)
        
        # タイトル設定
        title = slide.shapes.title
        if title:
            title.text = slide_content.title
            self._format_title(title)
        
        # AIで生成されたコンテンツを設定
        if len(slide.placeholders) > 1:
            content_placeholder = slide.placeholders[1]
            if content_placeholder.shape_type == MSO_SHAPE_TYPE.PLACEHOLDER:
                content_placeholder.text = slide_content.content
                self._format_content(content_placeholder)
        
        # SlideContentに含まれる画像を追加
        if include_images and slide_content.images:
            for i, image_url in enumerate(slide_content.images[:2]):
                self._add_image_to_slide(slide, image_url, i)
        
        # SlideContentに含まれるテーブルを追加
        if include_tables and slide_content.tables:
            for table_data in slide_content.tables[:1]:
                self._add_table_to_slide(slide, table_data)
        
        # 詳細情報があれば追加（information_agentからの生データ）
        detailed_content = information.get(f"slide_{slide_content.page_number}", {})
        if detailed_content:
            self._add_detailed_content(slide, detailed_content, include_images, include_tables)
        
        # ノート追加（ハルシネーション警告等）
        if slide_content.notes:
            notes_slide = slide.notes_slide
            notes_slide.notes_text_frame.text = slide_content.notes
    
    def _format_title(self, title_shape):
        """タイトルの書式設定"""
        if title_shape.has_text_frame:
            text_frame = title_shape.text_frame
            for paragraph in text_frame.paragraphs:
                paragraph.font.size = Pt(36)
                paragraph.font.bold = True
    
    def _format_content(self, content_shape):
        """コンテンツの書式設定"""
        if content_shape.has_text_frame:
            text_frame = content_shape.text_frame
            text_frame.auto_size = MSO_AUTO_SIZE.SHAPE_TO_FIT_TEXT
            
            for paragraph in text_frame.paragraphs:
                paragraph.font.size = Pt(18)
                paragraph.space_after = Pt(12)
    
    def _add_detailed_content(
        self, 
        slide, 
        detailed_content: Dict[str, Any],
        include_images: bool,
        include_tables: bool
    ):
        """詳細コンテンツを追加"""
        
        # テキストコンテンツの追加
        text_content = detailed_content.get("text", "")
        if text_content and len(slide.placeholders) > 1:
            content_placeholder = slide.placeholders[1]
            if hasattr(content_placeholder, 'text'):
                if content_placeholder.text:
                    content_placeholder.text += "\n\n" + text_content[:500]  # 長すぎる場合は切り詰め
                else:
                    content_placeholder.text = text_content[:500]
        
        # 画像の追加 - information_agentから収集された画像とAIが推奨する画像の両方を処理
        if include_images:
            # 既存の画像（information_agentから）
            existing_images = detailed_content.get("images", [])
            for i, image_url in enumerate(existing_images[:2]):  # 最大2つの画像
                self._add_image_to_slide(slide, image_url, i)
        
        # テーブルの追加 - information_agentで収集されたデータとAIが構造化したデータ
        if include_tables:
            # 既存のテーブル（information_agentから）
            existing_tables = detailed_content.get("tables", [])
            for table_data in existing_tables[:1]:  # 最大1つのテーブル
                self._add_table_to_slide(slide, table_data)
    
    def _add_image_to_slide(self, slide, image_url: str, position: int):
        """スライドに画像を追加"""
        try:
            # 画像をダウンロード
            response = requests.get(image_url, timeout=10)
            if response.status_code == 200:
                # 一時ファイルに保存
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_file:
                    tmp_file.write(response.content)
                    tmp_file_path = tmp_file.name
                
                # 画像サイズと位置を計算
                left = Inches(6) if position == 0 else Inches(6)
                top = Inches(2 + position * 2.5)
                width = Inches(3)
                
                # スライドに画像を追加
                slide.shapes.add_picture(tmp_file_path, left, top, width=width)
                
                # 一時ファイルを削除
                os.unlink(tmp_file_path)
        except Exception as e:
            print(f"Failed to add image {image_url}: {e}")
    
    def _add_table_to_slide(self, slide, table_data: Dict[str, Any]):
        """スライドにテーブルを追加"""
        try:
            # 様々な形式のテーブルデータに対応
            headers = []
            rows = []
            
            if isinstance(table_data, dict):
                if "headers" in table_data and "rows" in table_data:
                    # 標準形式: {"headers": [...], "rows": [[...]]}
                    headers = table_data.get("headers", [])
                    rows = table_data.get("rows", [])
                elif "data" in table_data:
                    # information_agentから: {"data": [[...]]}
                    data = table_data.get("data", [])
                    if data and len(data) > 0:
                        headers = data[0]  # 最初の行をヘッダーとして使用
                        rows = data[1:] if len(data) > 1 else []
                else:
                    # その他の形式を試す
                    for key, value in table_data.items():
                        if isinstance(value, list) and len(value) > 0:
                            if isinstance(value[0], list):
                                # リストのリスト形式
                                headers = value[0] if len(value) > 0 else []
                                rows = value[1:] if len(value) > 1 else []
                                break
            elif isinstance(table_data, list):
                # 直接リスト形式: [[...], [...]]
                if len(table_data) > 0:
                    headers = table_data[0] if isinstance(table_data[0], list) else []
                    rows = table_data[1:] if len(table_data) > 1 else []
            
            if not headers or not rows:
                print(f"Warning: Invalid table data format: {table_data}")
                return
            
            # テーブルの位置とサイズ
            left = Inches(0.5)
            top = Inches(4)
            width = Inches(9)
            height = Inches(2)
            
            # テーブル作成
            shape = slide.shapes.add_table(
                len(rows) + 1, len(headers), left, top, width, height
            )
            table = shape.table
            
            # ヘッダー設定
            for i, header in enumerate(headers):
                if i < len(table.columns):
                    cell = table.cell(0, i)
                    cell.text = str(header)
                    cell.text_frame.paragraphs[0].font.bold = True
            
            # データ行設定
            for row_idx, row in enumerate(rows):
                if row_idx + 1 < len(table.rows):
                    for col_idx, cell_data in enumerate(row):
                        if col_idx < len(headers) and col_idx < len(table.columns):
                            cell = table.cell(row_idx + 1, col_idx)
                            cell.text = str(cell_data)
        
        except Exception as e:
            print(f"Failed to add table: {e}")
            print(f"Table data was: {table_data}")

if __name__ == "__main__":
    agent_skills = [
        AgentSkill(
            name="create_slides",
            description="アジェンダと情報からPowerPointスライドを作成",
            id="create_slides",
            tags=[],
            input_modes=[],
            output_modes=[],
            examples=[]
        )
    ]
    
    # Agent setup
    agent_card = AgentCard(
        name="Slide Creation Agent",
        description="python-pptx を使用してPowerPointスライドを作成するエージェント",
        version="1.0.0",
        url=settings.slide_agent_url,
        skills=agent_skills,
        capabilities={},
        default_input_modes=[],
        default_output_modes=[]
    )

    executor = SlideCreationExecutor()
    task_store = InMemoryTaskStore()
    request_handler = DefaultRequestHandler(executor, task_store)

    # Create A2A application
    a2a_app = A2AStarletteApplication(agent_card, request_handler)

    uvicorn.run(a2a_app.build(), host="0.0.0.0", port=8003)
