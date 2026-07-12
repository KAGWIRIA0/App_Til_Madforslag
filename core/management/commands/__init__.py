"""
Management command: migrate_images_to_cloudinary

Scans all models with ImageField(s) and re-uploads any image that is
still sitting in local filesystem storage (MEDIA_ROOT) to whatever
storage backend is currently configured as default (Cloudinary, once
the STORAGES fix is deployed).

Usage:
    python manage.py migrate_images_to_cloudinary
    python manage.py migrate_images_to_cloudinary --dry-run

Run this AFTER deploying the STORAGES fix, so that re-saving the
field actually pushes the file to Cloudinary instead of writing it
back to local disk.
"""

import os

from django.apps import apps
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage, default_storage
from django.core.management.base import BaseCommand
from django.db import models


class Command(BaseCommand):
    help = "Re-upload images still on local disk storage to the current default storage (Cloudinary)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='List what would be migrated without actually uploading anything.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        # Explicit local filesystem storage, regardless of what
        # default_storage currently points to. This lets us find and
        # read files that were originally saved locally.
        local_storage = FileSystemStorage()

        self.stdout.write(self.style.NOTICE(
            f"Current default storage backend: {default_storage.__class__.__module__}.{default_storage.__class__.__name__}"
        ))

        if default_storage.__class__.__name__ == 'FileSystemStorage':
            self.stdout.write(self.style.ERROR(
                "default_storage is STILL FileSystemStorage. Deploy the STORAGES settings "
                "fix first, then run this command again — otherwise this will just copy "
                "files from local storage back to local storage."
            ))
            return

        total_found = 0
        total_migrated = 0
        total_missing = 0
        total_skipped = 0

        for model in apps.get_models():
            image_fields = [
                f for f in model._meta.get_fields()
                if isinstance(f, models.ImageField)
            ]
            if not image_fields:
                continue

            for field in image_fields:
                field_name = field.name
                qs = model.objects.exclude(**{f"{field_name}": ''}).exclude(**{f"{field_name}__isnull": True})

                for obj in qs:
                    file_field = getattr(obj, field_name)
                    if not file_field:
                        continue

                    name = file_field.name
                    total_found += 1

                    # Already a full Cloudinary-style URL/name? Skip.
                    if name.startswith('http://') or name.startswith('https://'):
                        total_skipped += 1
                        continue

                    if not local_storage.exists(name):
                        total_missing += 1
                        self.stdout.write(self.style.WARNING(
                            f"[MISSING] {model.__name__}.{field_name} (pk={obj.pk}): "
                            f"'{name}' not found on local disk — original file is gone, "
                            f"this record needs a manual re-upload."
                        ))
                        continue

                    if dry_run:
                        self.stdout.write(
                            f"[WOULD MIGRATE] {model.__name__}.{field_name} (pk={obj.pk}): '{name}'"
                        )
                        continue

                    try:
                        with local_storage.open(name, 'rb') as f:
                            content = f.read()

                        base_name = os.path.basename(name)
                        # save=True triggers a normal model save which uses
                        # the current default_storage (Cloudinary) to store
                        # the new file and updates the field's name/url.
                        file_field.save(base_name, ContentFile(content), save=True)

                        total_migrated += 1
                        self.stdout.write(self.style.SUCCESS(
                            f"[MIGRATED] {model.__name__}.{field_name} (pk={obj.pk}): "
                            f"'{name}' -> '{getattr(obj, field_name).name}'"
                        ))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(
                            f"[FAILED] {model.__name__}.{field_name} (pk={obj.pk}): '{name}' — {e}"
                        ))

        self.stdout.write("")
        self.stdout.write(self.style.NOTICE("Summary:"))
        self.stdout.write(f"  Total image fields found:  {total_found}")
        self.stdout.write(f"  Already remote (skipped):  {total_skipped}")
        if dry_run:
            self.stdout.write(f"  Would migrate:             {total_found - total_skipped - total_missing}")
        else:
            self.stdout.write(f"  Successfully migrated:     {total_migrated}")
        self.stdout.write(f"  Missing on local disk:     {total_missing}")

        if total_missing:
            self.stdout.write(self.style.WARNING(
                "\nRecords marked MISSING need their images re-uploaded manually "
                "through Django admin, since the original file no longer exists "
                "anywhere on disk (likely lost to Railway's ephemeral filesystem "
                "on a redeploy/restart)."
            ))