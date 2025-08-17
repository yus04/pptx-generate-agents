from opentelemetry import trace, metrics
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.resources import Resource
import logging

from .config import settings


class TelemetryManager:
    def __init__(self):
        self._tracer = None
        self._meter = None
        self.setup_telemetry()
    
    def setup_telemetry(self):
        """OpenTelemetry のセットアップ"""
        # Resource の設定
        resource = Resource.create({
            "service.name": settings.otel_service_name,
            "service.version": "1.0.0"
        })
        
        # Tracer の設定
        trace_provider = TracerProvider(resource=resource)
        
        if settings.otel_exporter_endpoint:
            # OTLP Exporter の設定
            otlp_exporter = OTLPSpanExporter(
                endpoint=settings.otel_exporter_endpoint,
                insecure=True
            )
            span_processor = BatchSpanProcessor(otlp_exporter)
            trace_provider.add_span_processor(span_processor)
        
        trace.set_tracer_provider(trace_provider)
        self._tracer = trace.get_tracer(__name__)
        
        # Metrics の設定
        if settings.otel_exporter_endpoint:
            metric_exporter = OTLPMetricExporter(
                endpoint=settings.otel_exporter_endpoint.replace("traces", "metrics"),
                insecure=True
            )
            metric_reader = PeriodicExportingMetricReader(
                exporter=metric_exporter,
                export_interval_millis=30000
            )
            meter_provider = MeterProvider(
                resource=resource,
                metric_readers=[metric_reader]
            )
        else:
            meter_provider = MeterProvider(resource=resource)
        
        metrics.set_meter_provider(meter_provider)
        self._meter = metrics.get_meter(__name__)
        
        # 自動インストルメンテーション
        self.setup_auto_instrumentation()
    
    def setup_auto_instrumentation(self):
        """自動インストルメンテーションの設定"""
        try:
            # FastAPI instrumentation
            FastAPIInstrumentor.instrument()
            
            # HTTP Client instrumentation
            HTTPXClientInstrumentor().instrument()
            RequestsInstrumentor().instrument()
            
        except Exception as e:
            logging.warning(f"Failed to setup auto instrumentation: {e}")
    
    def get_tracer(self):
        """Tracer インスタンスを取得"""
        return self._tracer
    
    def get_meter(self):
        """Meter インスタンスを取得"""
        return self._meter
    
    def trace_agent_operation(self, agent_name: str, operation: str):
        """エージェント操作のトレーシング用デコレータ"""
        def decorator(func):
            async def wrapper(*args, **kwargs):
                with self._tracer.start_as_current_span(
                    f"{agent_name}.{operation}",
                    attributes={
                        "agent.name": agent_name,
                        "agent.operation": operation
                    }
                ) as span:
                    try:
                        result = await func(*args, **kwargs)
                        span.set_attribute("operation.success", True)
                        return result
                    except Exception as e:
                        span.set_attribute("operation.success", False)
                        span.set_attribute("error.message", str(e))
                        span.record_exception(e)
                        raise
            return wrapper
        return decorator
    
    def create_counter(self, name: str, description: str = ""):
        """カウンターメトリクスを作成"""
        return self._meter.create_counter(
            name=name,
            description=description
        )
    
    def create_histogram(self, name: str, description: str = ""):
        """ヒストグラムメトリクスを作成"""
        return self._meter.create_histogram(
            name=name,
            description=description
        )


# Global instance
telemetry_manager = TelemetryManager()