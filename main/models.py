# Change this in main/models.py
import google.generativeai as genai
from django.db import models
from django.conf import settings as django_settings
import cv2
import numpy as np
import logging
import os

from PIL import Image
import io
import base64

from google import genai
from google.genai import types
import os

# Aapki API Key yahan set ho gayi hai
os.environ["GEMINI_API_KEY"] = "AQ.Ab8RN6JSooYPshmAr7NUAUEGPdk76Xne0Hb7VM_2FtJGUpdL1A"

from google import genai

logger = logging.getLogger(__name__)

# Gemini model to use for handwriting OCR.
# gemini-1.5-flash and gemini-2.0-flash have both been shut down by Google.
# gemini-3.5-flash is the current stable model as of June 2026.
GEMINI_MODEL_NAME = "gemini-3.5-flash"


def get_gemini_api_key():
    """
    Read the Gemini API key from the environment (or Django settings).
    NEVER hardcode API keys in source code.
    Set it before running the server, e.g.:
        export GEMINI_API_KEY="your-key-here"
    """
    api_key = os.environ.get("GEMINI_API_KEY") or getattr(django_settings, "GEMINI_API_KEY", None)
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Set it as an environment variable "
            "before starting the server, e.g. export GEMINI_API_KEY=your-key-here"
        )
    return api_key


class UploadedImage(models.Model):
    image = models.ImageField(upload_to='uploads/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_text = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Image uploaded at {self.uploaded_at}"

    def process_with_cnn(self):
        """Process the uploaded image with the Gemini model to extract text"""
        try:
            cnn = CNNTextRecognition()
            extracted_text = cnn.extract_text(self.image.path)
            self.processed_text = extracted_text
            self.save()
            return extracted_text
        except Exception as e:
            logger.error(f"Error processing image with CNN: {str(e)}")
            return f"Error: {str(e)}"


class CNNTextRecognition:
    """A class to handle handwriting text recognition using the Gemini API."""

    def __init__(self, api_key=None):
        self.client = genai.Client(api_key=api_key or get_gemini_api_key())

    def preprocess_image(self, image_path):
        try:
            img = cv2.imread(image_path)
            if img is None:
                raise ValueError("Could not read image file")
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
            preprocessed_path = image_path.replace('.', '_preprocessed.')
            cv2.imwrite(preprocessed_path, enhanced)
            return preprocessed_path
        except Exception as e:
            logger.error(f"Error preprocessing image: {str(e)}")
            return image_path

    def _load_image_part(self, image_path):
        with open(image_path, 'rb') as f:
            image_bytes = f.read()
        mime_type = "image/png" if image_path.lower().endswith(".png") else "image/jpeg"
        return types.Part.from_bytes(data=image_bytes, mime_type=mime_type)

    def extract_text(self, image_path, preprocess=True):
        try:
            path_to_use = self.preprocess_image(image_path) if preprocess else image_path
            image_part = self._load_image_part(path_to_use)
            prompt = (
                "Extract all text from this handwritten document. "
                "Return only the text content with no additional commentary."
            )
            response = self.client.models.generate_content(
                model=GEMINI_MODEL_NAME,
                contents=[prompt, image_part],
            )
            extracted_text = (response.text or "").strip()
            if not extracted_text:
                return "No text could be extracted from the image."
            return extracted_text
        except Exception as e:
            logger.error(f"Error extracting text with CNN: {str(e)}")
            return f"Error: {str(e)}"

    def extract_text_with_layout(self, image_path):
        try:
            image_part = self._load_image_part(image_path)
            prompt = """
            Extract all text from this document while preserving the layout.
            For each paragraph or section:
            1. Extract the text
            2. Note if it's a heading, bullet point, or normal paragraph
            3. Preserve any important formatting
            Return the content in a structured format.
            """
            response = self.client.models.generate_content(
                model=GEMINI_MODEL_NAME,
                contents=[prompt, image_part],
            )
            structured_text = (response.text or "").strip()
            return structured_text
        except Exception as e:
            logger.error(f"Error extracting text with layout: {str(e)}")
            return f"Error: {str(e)}"


class CNNResult(models.Model):
    image = models.ImageField(upload_to='cnn_images/')
    extracted_text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"CNN Result {self.id} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"

    def process_with_cnn(self):
        cnn = CNNTextRecognition()
        extracted_text = cnn.extract_text(self.image.path)
        self.extracted_text = extracted_text
        self.save()
        return extracted_text
