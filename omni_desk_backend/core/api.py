"""Version info, changelog, and migration status API endpoints."""

import os
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.db import connection
from django.db import migrations as django_migrations
from django.db.migrations.loader import MigrationLoader
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def version_info(request):
    import django
    return Response({
        'version': getattr(settings, 'APP_VERSION', '0.0.0-dev'),
        'build_time': getattr(settings, 'BUILD_TIME', 'unknown'),
        'django_version': f'{django.VERSION[0]}.{django.VERSION[1]}.{django.VERSION[2]}',
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def changelog(request):
    changelog_path = Path(__file__).resolve().parent.parent.parent.parent / 'deployment' / 'docker' / 'CHANGELOG.md'
    if changelog_path.is_file():
        content = changelog_path.read_text(encoding='utf-8')
    else:
        content = '# 更新日志\n\n暂无更新日志。'
    return Response({'changelog': content})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def migration_status(request):
    loader = MigrationLoader(connection)
    loader.build_graph()

    applied_list = []
    for app, name in sorted(loader.applied_migrations):
        applied_list.append({'app': app, 'name': name})

    pending_list = []
    destructive = False
    for app_config in apps.get_app_configs():
        app_label = app_config.label
        if not hasattr(app_config, 'migrations'):
            continue
        for migration in app_config.migrations:
            if migration.name.startswith('__'):
                continue
            key = (app_label, migration.name.replace('.py', ''))
            if key in loader.applied_migrations:
                continue

            ops = []
            for op in migration.operations:
                op_type = type(op).__name__
                if isinstance(op, django_migrations.DeleteModel):
                    ops.append({'type': op_type, 'model': op.name, 'destructive': True})
                    destructive = True
                elif isinstance(op, django_migrations.RemoveField):
                    ops.append({'type': op_type, 'model': op.model_name, 'field': op.name, 'destructive': True})
                    destructive = True
                elif isinstance(op, django_migrations.AddField):
                    ops.append({'type': op_type, 'model': op.model_name, 'field': op.name})
                elif isinstance(op, django_migrations.AlterField):
                    ops.append({'type': op_type, 'model': op.model_name, 'field': op.name})
                elif isinstance(op, django_migrations.CreateModel):
                    ops.append({'type': op_type, 'model': op.name})
                else:
                    ops.append({'type': op_type})

            pending_list.append({
                'app': app_label,
                'name': migration.name.replace('.py', ''),
                'operations': ops,
            })

    return Response({
        'applied': applied_list,
        'applied_count': len(applied_list),
        'pending': pending_list,
        'pending_count': len(pending_list),
        'has_destructive': destructive,
    })
