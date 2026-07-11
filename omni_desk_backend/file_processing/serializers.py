from rest_framework import serializers
from .models import UploadedFile, ProcessingResult, AIAnalysis


class UploadedFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UploadedFile
        fields = [
            'id', 'original_filename', 'file_size', 'mime_type',
            'status', 'error_message', 'sheet_count', 'page_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'status', 'error_message', 'sheet_count', 'page_count', 'created_at', 'updated_at']


class ProcessingResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProcessingResult
        fields = [
            'id', 'content_text', 'content_markdown', 'content_json',
            'sheets_data', 'row_count', 'column_count', 'processed_at'
        ]


class AIAnalysisSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIAnalysis
        fields = [
            'id', 'analysis_type', 'query_text', 'result_text',
            'result_data', 'model_used', 'tokens_used',
            'processing_time_ms', 'created_at'
        ]
