from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.prompt_template import PromptTemplateConfig, InputVariable
from semantic_kernel.functions import KernelArguments
from typing import Dict, Any
from pptx import Presentation
import io
import json
import uvicorn
import uuid

from a2a.types import AgentCard, AgentSkill, DataPart, Message, TextPart, Part, Role
from a2a.server.tasks.inmemory_task_store import InMemoryTaskStore
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.apps import A2AStarletteApplication
from a2a.server.agent_execution import AgentExecutor
from a2a.server.agent_execution import RequestContext
from a2a.server.events.event_queue import EventQueue

from shared.config import settings
from shared.storage.blob_client import blob_client


class ReviewExecutor(AgentExecutor):
    def __init__(self):
        self.kernel = Kernel()
        
        # Azure OpenAI service setup
        self.chat_service = AzureChatCompletion(
            deployment_name=settings.azure_ai_foundry_model_deployment,
            endpoint=settings.azure_ai_foundry_chat_endpoint,
            api_key=settings.azure_ai_foundry_key
        )
        self.kernel.add_service(self.chat_service)
        
        self._setup_prompts()
    
    def _setup_prompts(self):
        """レビュー用プロンプトテンプレートを設定"""
        review_prompt = """
あなたは PowerPoint スライドの品質チェックと事実確認の専門家です。
生成されたスライドの内容を詳細にレビューし、以下の観点で評価してください。

## レビュー観点
1. **事実の正確性**: 内容に事実誤認や古い情報がないか
2. **論理的整合性**: スライド間の論理的なつながりが適切か
3. **情報の完全性**: 必要な情報が不足していないか
4. **プレゼンテーション効果**: 聴衆にとって理解しやすい構成か
5. **ハルシネーション検出**: AI生成特有の事実でない内容がないか
6. **アジェンダとの整合性**: 計画されたコンテンツと実際のコンテンツの整合性

## 入力情報
元のアジェンダ: {{$agenda}}
実際のスライドコンテンツ: {{$slide_contents}}

## 各スライドの分析
各スライドについて以下の情報を分析してください：
- スライド番号とタイトル
- 計画されたコンテンツ vs 実際のコンテンツ
- 含まれているテキスト、画像、テーブル
- 事実確認が必要な箇所

## 出力要件
以下のJSON形式で出力してください：
```json
{
  "overall_score": 95,
  "issues": [
    {
      "slide_number": 3,
      "type": "hallucination",
      "severity": "medium",
      "description": "統計データの出典が不明確",
      "suggestion": "出典を明記するか、より信頼性の高いデータに置き換える"
    }
  ],
  "quality_checks": {
    "factual_accuracy": 90,
    "logical_consistency": 95,
    "completeness": 88,
    "presentation_effectiveness": 92,
    "hallucination_risk": 15,
    "agenda_alignment": 88
  },
  "recommendations": [
    "スライド3の統計データに出典を追加",
    "スライド7の図表をより見やすく調整"
  ],
  "notes_for_slides": {
    "3": "統計データの出典要確認 - 2023年のデータの最新性を要チェック",
    "7": "図表の視認性について要確認"
  }
}
```

レビューを実行してください：
"""
        
        prompt_config = PromptTemplateConfig(
            template=review_prompt,
            name="slide_review",
            description="スライド品質レビューとハルシネーション検出",
            input_variables=[
                InputVariable(name="agenda", description="元のアジェンダ情報"),
                InputVariable(name="slide_contents", description="実際のスライドコンテンツ")
            ]
        )
        
        self.review_function = self.kernel.add_function(
            plugin_name="ReviewPlugin",
            function_name="review_slides",
            prompt_template_config=prompt_config
        )
    
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """スライドレビューを実行"""
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
            slide_url = payload.get("slide_url", "")
            agenda = payload.get("agenda", {})
            slide_contents = payload.get("slide_contents", [])
            print(f"   ✓ Received slide_url: {slide_url}")
            print(f"   ✓ Received agenda with {len(agenda.get('slides', []))} slides")
            print(f"   ✓ Received slide_contents with {len(slide_contents)} slides")
            
            if not slide_url:
                print("✗ Error: slide url is required")
                return
            
            # 実際のPowerPointファイルの内容を取得・分析
            print("   → Downloading and analyzing PowerPoint file...")
            actual_slide_content = await self._analyze_slide_content(slide_url)
            
            if actual_slide_content.get("error"):
                print(f"✗ Error analyzing slide: {actual_slide_content['error']}")
                # エラーの場合でも、提供されたslide_contentsを使用してレビューを続行
                print("   → Continuing with provided slide_contents...")
            else:
                print(f"   ✓ Successfully analyzed {actual_slide_content.get('total_slides', 0)} slides")
                # 実際のファイル内容と提供されたコンテンツを統合
                slide_contents = self._merge_slide_contents(slide_contents, actual_slide_content)
            
            # Semantic Kernel でレビュー実行
            print("   → Performing AI-powered slide review...")
            arguments = KernelArguments(
                agenda=json.dumps(agenda, ensure_ascii=False, indent=2),
                slide_contents=json.dumps(slide_contents, ensure_ascii=False, indent=2)
            )
            
            result = await self.kernel.invoke(self.review_function, arguments)
            review_text = str(result)
            
            # JSON パース
            try:
                if isinstance(review_text, dict):
                    review_data = review_text
                else:
                    review_text = str(result)
                
                print(f"   ✓ Review result type: {type(review_text)}")
                print(f"   ✓ Review text preview: {review_text[:200]}...")
                
                # JSONブロックを抽出
                if "```json" in review_text:
                    json_start = review_text.find("```json") + 7
                    json_end = review_text.find("```", json_start)
                    review_json = review_text[json_start:json_end].strip()
                else:
                    review_json = review_text.strip()
                
                print(f"   ✓ Extracted JSON preview: {review_json[:200]}...")
                
                # JSON文字列をパース
                review_data = json.loads(review_json)
                print(f"   ✓ Successfully parsed review JSON")
                print(f"   ✓ Overall score: {review_data.get('overall_score', 'N/A')}")
                print(f"   ✓ Issues found: {len(review_data.get('issues', []))}")
                print(f"   ✓ Notes for slides: {len(review_data.get('notes_for_slides', {}))}")
                
                # 重要: ハルシネーション警告をPowerPointファイルのノートとして実際に追加
                print("   → Adding warning notes to PowerPoint file...")
                notes_added = await self._add_warning_notes(slide_url, review_data)
                if notes_added:
                    print("   ✓ Successfully added warning notes to PowerPoint file")
                else:
                    print("   ⚠ Warning notes could not be added to PowerPoint file")
                
                # 結果をEventQueueに送信
                message = Message(
                    message_id=str(uuid.uuid4()),
                    role=Role.agent,
                    context_id=context.message.context_id,
                    parts=[Part(root=TextPart(text=review_text))]
                )
                await event_queue.enqueue_event(message)
                print(f"   ✓ Review result sent to EventQueue: {len(review_text)} characters")
                
            except (json.JSONDecodeError, ValueError) as e:
                print(f"   ✗ JSON parsing error: {str(e)}")
                # フォールバック: 基本的なレビュー結果
                fallback_review = self._create_fallback_review()
                result_json = json.dumps(fallback_review, ensure_ascii=False)
                message = Message(
                    message_id=str(uuid.uuid4()),
                    role=Role.agent,
                    context_id=context.message.context_id if hasattr(context, 'message') and hasattr(context.message, 'context_id') else str(uuid.uuid4()),
                    parts=[Part(root=TextPart(text=result_json))]
                )
                await event_queue.enqueue_event(message)
                print(f"   ✓ Fallback result sent to EventQueue")
        
        except Exception as e:
            print(f"✗ Error during pptx review: {str(e)}")
            import traceback
            traceback.print_exc()
    
    async def cancel(self, request_id: str) -> bool:
        """処理をキャンセル"""
        return True
    
    async def _analyze_slide_content(self, slide_url: str) -> Dict[str, Any]:
        """スライドの内容を分析"""
        try:
            print(f"      Downloading file from: {slide_url}")
            
            # Blob Storage からファイルをダウンロード
            file_data = blob_client.download_file(slide_url)
            if not file_data:
                print(f"      ✗ Failed to download file from blob storage")
                return {"error": "Failed to download slide file"}
            
            print(f"      ✓ Downloaded file: {len(file_data)} bytes")
            
            # PowerPoint ファイル解析
            slide_content = await self._parse_powerpoint_content(file_data)
            return slide_content
            
        except Exception as e:
            print(f"      ✗ Failed to analyze slide content: {e}")
            return {"error": str(e)}
    
    async def _parse_powerpoint_content(self, file_data: bytes) -> Dict[str, Any]:
        """PowerPoint ファイルの内容を解析"""
        try:
            print(f"      Parsing PowerPoint file...")
            
            # BytesIO でファイルを開く
            pptx_file = io.BytesIO(file_data)
            prs = Presentation(pptx_file)
            
            slides_content = []
            for i, slide in enumerate(prs.slides):
                slide_text = []
                images = []
                tables = []
                
                # テキストシェイプから内容を抽出
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        slide_text.append(shape.text.strip())
                    
                    # 画像の検出
                    if shape.shape_type == 13:  # Picture type
                        images.append({"type": "image", "description": "画像が含まれています"})
                    
                    # テーブルの検出
                    if hasattr(shape, "table"):
                        table_data = []
                        for row in shape.table.rows:
                            row_data = []
                            for cell in row.cells:
                                row_data.append(cell.text.strip())
                            table_data.append(row_data)
                        tables.append({"type": "table", "data": table_data})
                
                # スライドタイトルの抽出（最初のテキストシェイプをタイトルと仮定）
                title = slide_text[0] if slide_text else f"スライド {i + 1}"
                
                slides_content.append({
                    "slide_number": i + 1,
                    "title": title,
                    "actual_text": "\n".join(slide_text),
                    "images": images,
                    "tables": tables,
                    "shape_count": len(slide.shapes)
                })
            
            print(f"      ✓ Parsed {len(slides_content)} slides successfully")
            
            return {
                "total_slides": len(prs.slides),
                "slides": slides_content
            }
            
        except Exception as e:
            print(f"      ✗ Failed to parse PowerPoint: {e}")
            return {"error": "Failed to parse PowerPoint file"}
    
    def _merge_slide_contents(self, provided_contents: list, actual_contents: Dict[str, Any]) -> list:
        """提供されたコンテンツと実際のファイル内容をマージ"""
        try:
            if actual_contents.get("error"):
                return provided_contents
            
            actual_slides = actual_contents.get("slides", [])
            merged_contents = []
            
            for i, provided_slide in enumerate(provided_contents):
                # 実際のスライドデータを取得
                actual_slide = None
                if i < len(actual_slides):
                    actual_slide = actual_slides[i]
                
                # マージされたコンテンツを作成
                merged_slide = provided_slide.copy()
                if actual_slide:
                    merged_slide.update({
                        "actual_text": actual_slide.get("actual_text", ""),
                        "images": actual_slide.get("images", []),
                        "tables": actual_slide.get("tables", []),
                        "shape_count": actual_slide.get("shape_count", 0)
                    })
                
                merged_contents.append(merged_slide)
            
            print(f"      ✓ Merged {len(merged_contents)} slide contents")
            return merged_contents
            
        except Exception as e:
            print(f"      ✗ Error merging slide contents: {e}")
            return provided_contents
    
    async def _add_warning_notes(self, slide_url: str, review_data: Dict[str, Any]) -> bool:
        """ハルシネーション警告等をPowerPointのノートに追加"""
        try:
            notes_for_slides = review_data.get("notes_for_slides", {})
            issues = review_data.get("issues", [])
            
            if not notes_for_slides and not issues:
                print(f"      No notes or issues to add")
                return True
            
            print(f"      Adding notes to slides: {list(notes_for_slides.keys())}")
            print(f"      Adding issue warnings for {len(issues)} issues")
            
            # Blob Storage からファイルをダウンロード
            file_data = blob_client.download_file(slide_url)
            if not file_data:
                print(f"      ✗ Failed to download file for note addition")
                return False
            
            print(f"      ✓ Downloaded file for modification: {len(file_data)} bytes")
            
            # PowerPoint ファイルを開く
            pptx_file = io.BytesIO(file_data)
            prs = Presentation(pptx_file)
            
            # issuesからスライド別の警告をまとめる
            slide_warnings = {}
            for issue in issues:
                slide_num = str(issue.get('slide_number', ''))
                if slide_num:
                    if slide_num not in slide_warnings:
                        slide_warnings[slide_num] = []
                    severity = issue.get('severity', 'medium')
                    issue_type = issue.get('type', 'unknown')
                    description = issue.get('description', '')
                    suggestion = issue.get('suggestion', '')
                    
                    warning_text = f"⚠️ [{severity.upper()}] {issue_type}: {description}"
                    if suggestion:
                        warning_text += f"\n💡 推奨: {suggestion}"
                    
                    slide_warnings[slide_num].append(warning_text)
            
            # 各スライドにノートを追加
            notes_added = 0
            for slide_num_str in set(list(notes_for_slides.keys()) + list(slide_warnings.keys())):
                slide_num = int(slide_num_str) - 1  # 0ベースのインデックス
                if slide_num < len(prs.slides):
                    slide = prs.slides[slide_num]
                    notes_slide = slide.notes_slide
                    
                    # 既存のノートを取得
                    existing_text = ""
                    if notes_slide.notes_text_frame.text:
                        existing_text = notes_slide.notes_text_frame.text
                    
                    # 新しいノートを構築
                    new_notes = []
                    
                    # レビューノートを追加
                    if slide_num_str in notes_for_slides:
                        note_text = notes_for_slides[slide_num_str]
                        new_notes.append(f"📋 レビューノート: {note_text}")
                    
                    # 警告を追加
                    if slide_num_str in slide_warnings:
                        new_notes.extend(slide_warnings[slide_num_str])
                    
                    if new_notes:
                        # 日付とタイムスタンプを追加
                        from datetime import datetime
                        timestamp = datetime.now().strftime("%Y/%m/%d %H:%M")
                        
                        new_note_text = f"\n\n--- AI レビュー結果 ({timestamp}) ---\n"
                        new_note_text += "\n".join(new_notes)
                        
                        # 既存のノートに追加
                        notes_slide.notes_text_frame.text = existing_text + new_note_text
                        notes_added += 1
                        
                        print(f"      ✓ Added notes to slide {slide_num + 1}")
            
            if notes_added > 0:
                # ファイルを再アップロード
                output = io.BytesIO()
                prs.save(output)
                output.seek(0)
                
                print(f"      Uploading modified file...")
                
                # URLからファイルパスとBlob名を抽出
                # slide_url の形式: https://storageaccount.blob.core.windows.net/container/path/to/file.pptx
                # または相対パス: user_id/presentations/year/month/day/filename.pptx
                
                try:
                    # blob_client.upload_file_from_bytes を使用してより確実にアップロード
                    upload_success = blob_client.upload_file_from_bytes(
                        output.getvalue(), 
                        slide_url  # 元のURLと同じパスに上書き
                    )
                    
                    if upload_success:
                        print(f"      ✓ Successfully uploaded modified PowerPoint with {notes_added} slides updated to {slide_url}")
                        return True
                    else:
                        print(f"      ✗ Failed to upload modified PowerPoint to {slide_url}")
                        return False
                        
                except Exception as upload_error:
                    print(f"      ✗ Upload error: {upload_error}")
                    # フォールバック: 従来の方法でアップロード
                    try:
                        filename = slide_url.split("/")[-1]
                        # URL構造: .../user_id/presentations/year/month/day/filename
                        url_parts = slide_url.split("/")
                        user_id = "default_user"  # デフォルト値
                        for i, part in enumerate(url_parts):
                            if part == "presentations" and i > 0:
                                user_id = url_parts[i-1]
                                break
                        
                        upload_success = blob_client.upload_bytes(
                            output.getvalue(), filename, user_id, "presentations"
                        )
                        
                        if upload_success:
                            print(f"      ✓ Successfully uploaded modified PowerPoint with fallback method")
                            return True
                        else:
                            print(f"      ✗ Failed to upload modified PowerPoint with fallback method")
                            return False
                    except Exception as fallback_error:
                        print(f"      ✗ Fallback upload also failed: {fallback_error}")
                        return False
            else:
                print(f"      No notes were added")
                return True
            
        except Exception as e:
            print(f"      ✗ Failed to add warning notes: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _create_fallback_review(self) -> Dict[str, Any]:
        """フォールバック用の基本レビュー結果"""
        return {
            "overall_score": 85,
            "issues": [],
            "quality_checks": {
                "factual_accuracy": 85,
                "logical_consistency": 90,
                "completeness": 80,
                "presentation_effectiveness": 85,
                "hallucination_risk": 20
            },
            "recommendations": [
                "内容の事実確認を行ってください",
                "参考資料の出典を確認してください"
            ],
            "notes_for_slides": {}
        }

if __name__ == "__main__":
    agent_skills = [
        AgentSkill(
            name="review_slides",
            description="スライドの品質チェックとハルシネーション検出",
            id="review_slides",
            tags=[],
            input_modes=[],
            output_modes=[],
            examples=[]
        )
    ]

    # Agent setup
    agent_card = AgentCard(
        name="Review Agent",
        description="PowerPoint スライドの品質チェックとハルシネーション検出を行うエージェント",
        version="1.0.0",
        url=settings.review_agent_url,
        skills=agent_skills,
        capabilities={},
        default_input_modes=[],
        default_output_modes=[]
    )

    executor = ReviewExecutor()
    task_store = InMemoryTaskStore()
    request_handler = DefaultRequestHandler(executor, task_store)

    # Create A2A application
    a2a_app = A2AStarletteApplication(agent_card, request_handler)

    uvicorn.run(a2a_app.build(), host="0.0.0.0", port=8004)
