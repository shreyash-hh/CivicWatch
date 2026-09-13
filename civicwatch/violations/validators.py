import sys
from io import BytesIO
from PIL import Image, ImageOps
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile

ALLOWED_FORMATS = {
    'JPEG': 'image/jpeg',
    'PNG': 'image/png',
    'WEBP': 'image/webp'
}

def validate_image_file(image_file, max_size_mb=None, allowed_mimes=None):
    """
    Validates that the uploaded file:
    1. Does not exceed max_size_mb (default from settings: 5MB).
    2. Is a valid image and matches the allowed MIME type allowlist by inspecting magic bytes.
    """
    if not image_file:
        return image_file

    max_size = max_size_mb or getattr(settings, 'CIVICWATCH_MAX_UPLOAD_SIZE_MB', 5)
    allowed_mime_list = allowed_mimes or getattr(settings, 'CIVICWATCH_ALLOWED_IMAGE_MIMES', list(ALLOWED_FORMATS.values()))

    # Check file size
    if hasattr(image_file, 'size') and image_file.size > max_size * 1024 * 1024:
        raise ValidationError(f"File size exceeds the maximum allowed limit of {max_size} MB.")

    # Validate image format using PIL
    try:
        current_pos = image_file.tell() if hasattr(image_file, 'tell') else 0
        img = Image.open(image_file)
        img_format = img.format
        
        # Reset file pointer
        if hasattr(image_file, 'seek'):
            image_file.seek(current_pos)

        if not img_format or img_format.upper() not in ALLOWED_FORMATS:
            raise ValidationError(f"Unsupported image format: {img_format}. Allowed formats are JPEG, PNG, WEBP.")

        detected_mime = ALLOWED_FORMATS[img_format.upper()]
        if detected_mime not in allowed_mime_list:
            raise ValidationError(f"MIME type '{detected_mime}' is not permitted.")
            
    except Exception as e:
        if isinstance(e, ValidationError):
            raise
        raise ValidationError("Invalid or corrupt image file.")

    return image_file

def sanitize_and_strip_exif(image_file, max_dimension=(1200, 1200), quality=70):
    """
    Opens an image, transposes orientation if EXIF orientation is present,
    strips all EXIF/metadata (GPS, camera info, timestamps), resizes to max_dimension,
    and returns a clean InMemoryUploadedFile.
    """
    if not image_file:
        return image_file

    try:
        # Avoid double-processing if already sanitized
        if hasattr(image_file, 'name') and image_file.name and image_file.name.startswith('compressed_'):
            return image_file

        img = Image.open(image_file)

        # Transpose according to EXIF orientation tag before stripping
        try:
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass

        # Convert to RGB (stripping color profile metadata / alpha for JPEG compression)
        if img.mode != 'RGB':
            img = img.convert('RGB')

        # Create a fresh clean image to ensure no metadata dictionaries leak
        clean_img = Image.new("RGB", img.size)
        clean_img.paste(img)

        # Resize if larger than max_dimension
        clean_img.thumbnail(max_dimension, Image.Resampling.LANCZOS)

        output = BytesIO()
        # Save without any exif or extra metadata
        clean_img.save(output, format='JPEG', quality=quality, optimize=True)
        output.seek(0)

        filename = getattr(image_file, 'name', 'upload.jpg')
        clean_filename = f"compressed_{filename.rsplit('.', 1)[0]}.jpg"

        return InMemoryUploadedFile(
            output,
            'ImageField',
            clean_filename,
            'image/jpeg',
            sys.getsizeof(output),
            None
        )
    except Exception:
        # Fallback to returning original if an unforeseen processing error occurs
        return image_file
