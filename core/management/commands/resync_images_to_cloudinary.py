# import os
# from django.core.management.base import BaseCommand
# from django.core.files import File
# from django.apps import apps
# from django.conf import settings
# from django.db.models import ImageField, FileField


# class Command(BaseCommand):
#     help = "Re-uploads existing local media images to Cloudinary and updates DB references."

#     def add_arguments(self, parser):
#         parser.add_argument(
#             "--dry-run",
#             action="store_true",
#             help="Show what would be updated without actually saving.",
#         )

#     def handle(self, *args, **options):
#         dry_run = options["dry_run"]
#         media_root = settings.MEDIA_ROOT

#         total_checked = 0
#         total_fixed = 0
#         total_missing = 0

#         for model in apps.get_app_config("core").get_models():
#             image_fields = [
#                 f.name for f in model._meta.get_fields()
#                 if isinstance(f, (ImageField, FileField))
#             ]

#             if not image_fields:
#                 continue

#             for obj in model.objects.all():
#                 for field_name in image_fields:
#                     field_file = getattr(obj, field_name)

#                     if not field_file:
#                         continue

#                     total_checked += 1
#                     local_path = os.path.join(media_root, field_file.name)

#                     if not os.path.exists(local_path):
#                         self.stdout.write(
#                             self.style.WARNING(
#                                 f"[MISSING] {model.__name__} id={obj.id} "
#                                 f"{field_name}='{field_file.name}' not found locally, skipping."
#                             )
#                         )
#                         total_missing += 1
#                         continue

#                     self.stdout.write(
#                         f"[FOUND] {model.__name__} id={obj.id} {field_name} "
#                         f"-> {local_path}"
#                     )

#                     if dry_run:
#                         continue

#                     with open(local_path, "rb") as f:
#                         filename = os.path.basename(field_file.name)
#                         field_file.save(filename, File(f), save=True)

#                     total_fixed += 1
#                     self.stdout.write(
#                         self.style.SUCCESS(f"  -> re-uploaded to Cloudinary as {getattr(obj, field_name).name}")
#                     )

#         self.stdout.write(self.style.SUCCESS(
#             f"\nDone. Checked {total_checked} fields, fixed {total_fixed}, missing {total_missing}."
#         ))