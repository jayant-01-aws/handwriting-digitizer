from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import CNNResult
from .utils import extract_text_handwriting
import os
import logging
from django.conf import settings

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create your views here.

def index(request):
    return render(request, 'index.html')

def about(request):
    return render(request, 'about.html')
def digitize(request):
    if request.method == 'POST' and request.FILES.get('image'):
        try:
            image = request.FILES['image']
            logger.info(f"Received image: {image.name}")
            
            # Create the uploads directory if it doesn't exist
            upload_dir = os.path.join('media', 'cnn_images')
            os.makedirs(upload_dir, exist_ok=True)
            
            # Save the uploaded image
            cnn_result = CNNResult.objects.create(image=image)
            logger.info(f"Image saved at: {cnn_result.image.path}")
            
            # Process the image and extract text
            try:
                # Use Gemini-based CNN for text extraction
                extracted_text = cnn_result.process_with_cnn()
                logger.info("Text extraction completed")

                # If extraction failed internally, it returns a string starting with "Error:"
                if extracted_text.startswith("Error:"):
                    logger.error(extracted_text)
                    return JsonResponse({
                        'success': False,
                        'error': extracted_text
                    })

                # No need to update cnn_result.extracted_text or save again,
                # as process_with_cnn already does this.

                return JsonResponse({
                    'success': True,
                    'extracted_text': extracted_text,
                    'image_url': cnn_result.image.url
                })
            except RuntimeError as e:
                # Raised when GEMINI_API_KEY is missing
                logger.error(f"Configuration error: {str(e)}")
                return JsonResponse({
                    'success': False,
                    'error': str(e)
                })
            except Exception as e:
                logger.error(f"Error processing image: {str(e)}")
                return JsonResponse({
                    'success': False,
                    'error': f"Error processing image: {str(e)}"
                })
        except Exception as e:
            logger.error(f"Error handling upload: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': f"Error handling upload: {str(e)}"
            })
    
    return render(request, 'digitize.html')

def contact(request):
    return render(request, 'contact.html')
