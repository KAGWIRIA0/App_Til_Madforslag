import cloudinary
import cloudinary.uploader
from django.core.management.base import BaseCommand
from django.conf import settings
from core.models import (
    Dish, DishStewOption, GymFood,
    ComradeMeal, ComradeMealStewOption,
    SkinFood, WellnessFood
)
import os
from dotenv import load_dotenv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(BASE_DIR / '.env')


class Command(BaseCommand):
    help = 'Push all existing local media images to Cloudinary'

    def handle(self, *args, **kwargs):

        # Explicitly configure Cloudinary from env vars
        cloudinary.config(
            cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
            api_key=os.getenv('CLOUDINARY_API_KEY'),
            api_secret=os.getenv('CLOUDINARY_API_SECRET'),
            secure=True,
        )

        # Verify credentials loaded correctly before proceeding
        cfg = cloudinary.config()
        if not cfg.api_key:
            self.stdout.write(self.style.ERROR(
                '\n❌ Cloudinary API key not found!'
                '\nMake sure your .env file has:'
                '\n  CLOUDINARY_CLOUD_NAME=...'
                '\n  CLOUDINARY_API_KEY=...'
                '\n  CLOUDINARY_API_SECRET=...'
            ))
            return

        self.stdout.write(self.style.SUCCESS(
            f'✓ Cloudinary configured: cloud_name={cfg.cloud_name}'
        ))

        # List every model and its image field
        models_fields = [
            (Dish,                  'image'),
            (DishStewOption,        'image'),
            (GymFood,               'image'),
            (ComradeMeal,           'image'),
            (ComradeMealStewOption, 'image'),
            (SkinFood,              'image'),
            (WellnessFood,          'image'),
        ]

        total_uploaded = 0
        total_skipped  = 0
        total_failed   = 0

        for Model, field_name in models_fields:
            model_name = Model.__name__
            self.stdout.write(f'\n── {model_name} ──')

            for obj in Model.objects.all():
                image_field = getattr(obj, field_name)

                # Skip if no image saved
                if not image_field or not image_field.name:
                    total_skipped += 1
                    continue

                # Build full local path
                local_path = os.path.join(
                    settings.MEDIA_ROOT,
                    str(image_field.name)
                )

                # Skip if file doesn't exist on disk
                if not os.path.exists(local_path):
                    self.stdout.write(self.style.WARNING(
                        f'  MISSING FILE: {obj} → {image_field.name}'
                    ))
                    total_skipped += 1
                    continue

                try:
                    # public_id preserves your folder structure
                    public_id = image_field.name.rsplit('.', 1)[0]

                    result = cloudinary.uploader.upload(
                        local_path,
                        public_id=public_id,
                        overwrite=True,
                        resource_type='image',
                    )

                    # Save the new Cloudinary path back to the object
                    new_name = result['public_id'] + '.' + result['format']
                    image_field.name = new_name
                    obj.save(update_fields=[field_name])

                    self.stdout.write(self.style.SUCCESS(
                        f'  ✓ {obj} → {result["secure_url"]}'
                    ))
                    total_uploaded += 1

                except Exception as e:
                    self.stdout.write(self.style.ERROR(
                        f'  ✗ FAILED: {obj} → {e}'
                    ))
                    total_failed += 1

        # Summary
        self.stdout.write('\n' + '─' * 40)
        self.stdout.write(self.style.SUCCESS(f'✓ Uploaded : {total_uploaded}'))
        self.stdout.write(self.style.WARNING(f'  Skipped  : {total_skipped}'))
        if total_failed:
            self.stdout.write(self.style.ERROR(f'✗ Failed   : {total_failed}'))
        else:
            self.stdout.write(self.style.SUCCESS('✓ No failures!'))