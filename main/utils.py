import numpy as np
import cv2
import pytesseract
from PIL import Image
import os
from django.conf import settings
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def preprocess_image_for_handwriting(image):
    """
    Advanced preprocessing specifically for handwritten text using only OpenCV
    """
    try:
        # Convert to grayscale
        if len(image.shape) == 3 and image.shape[2] == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        # Increase contrast with CLAHE (Contrast Limited Adaptive Histogram Equalization)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        
        # Noise removal with bilateral filter (preserves edges)
        denoised = cv2.bilateralFilter(enhanced, 9, 75, 75)
        
        # Thresholding using Otsu's method
        _, thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Dilation to connect broken lines in handwriting
        kernel = np.ones((2, 2), np.uint8)
        dilated = cv2.dilate(thresh, kernel, iterations=1)
        
        # Erosion to reduce blob size
        eroded = cv2.erode(dilated, kernel, iterations=1)
        
        return eroded
    except Exception as e:
        logger.error(f"Error in preprocess_image_for_handwriting: {str(e)}")
        raise

def improve_image_for_ocr(image):
    """
    Apply multiple image processing techniques to enhance handwritten text recognition
    """
    try:
        # Make a copy
        img = image.copy()
        
        # Convert to grayscale if needed
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img
        
        # Apply a range of processing techniques
        techniques = []
        
        # Technique 1: Basic thresholding
        _, thresh1 = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        techniques.append(("binary_threshold", thresh1))
        
        # Technique 2: Otsu's thresholding
        _, thresh2 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        techniques.append(("otsu_threshold", thresh2))
        
        # Technique 3: Adaptive thresholding
        thresh3 = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                      cv2.THRESH_BINARY, 11, 2)
        techniques.append(("adaptive_threshold", thresh3))
        
        # Technique 4: CLAHE + Otsu
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        _, thresh4 = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        techniques.append(("clahe_otsu", thresh4))
        
        # Technique 5: Bilateral filtering + thresholding
        bilateral = cv2.bilateralFilter(gray, 9, 75, 75)
        _, thresh5 = cv2.threshold(bilateral, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        techniques.append(("bilateral_otsu", thresh5))
        
        # Technique 6: Dilation + erosion (morphological operations)
        kernel = np.ones((2, 2), np.uint8)
        dilated = cv2.dilate(thresh2, kernel, iterations=1)
        eroded = cv2.erode(dilated, kernel, iterations=1)
        techniques.append(("morph_operations", eroded))
        
        return techniques
    except Exception as e:
        logger.error(f"Error in improve_image_for_ocr: {str(e)}")
        raise

def process_with_multiple_psm(image):
    """
    Try various page segmentation modes with Tesseract
    to find the best result for handwritten text
    """
    try:
        results = []
        
        # PSM modes good for handwriting
        psm_modes = [
            (6, "Assume a single uniform block of text"),
            (11, "Sparse text. Find as much text as possible in no particular order"),
            (12, "Sparse text with OSD"),
            (13, "Raw line. Treat the image as a single text line")
        ]
        
        for psm_id, psm_desc in psm_modes:
            try:
                custom_config = f'--oem 3 --psm {psm_id} -l eng'
                text = pytesseract.image_to_string(image, config=custom_config)
                text = text.strip()
                # Count valid characters to rank result quality
                valid_char_count = sum(1 for c in text if c.isalnum() or c.isspace())
                
                results.append({
                    'mode': psm_id,
                    'desc': psm_desc,
                    'text': text,
                    'valid_chars': valid_char_count,
                    'length': len(text)
                })
                
                logger.info(f"PSM {psm_id} ({psm_desc}) produced {len(text)} chars")
            except Exception as e:
                logger.error(f"Error with PSM {psm_id}: {str(e)}")
        
        # Sort by valid character count (higher is better)
        results.sort(key=lambda x: x['valid_chars'], reverse=True)
        return results
    except Exception as e:
        logger.error(f"Error in process_with_multiple_psm: {str(e)}")
        raise

def extract_text_handwriting(image_path):
    """
    Extract text from handwritten document using multiple techniques
    and combining the results.
    """
    try:
        # Load the image
        image = cv2.imread(image_path)
        if image is None:
            return "Error: Could not load image"
        
        # Get various processed versions of the image
        processed_images = improve_image_for_ocr(image)
        
        # Store results from all techniques
        all_results = []
        
        # Try OCR with different processing techniques and PSM modes
        for technique_name, processed_img in processed_images:
            logger.info(f"Processing with technique: {technique_name}")
            
            # Convert to PIL Image for Tesseract
            pil_img = Image.fromarray(processed_img)
            
            # Try different PSM modes
            psm_results = process_with_multiple_psm(pil_img)
            
            # Add technique info to results
            for result in psm_results:
                result['technique'] = technique_name
                all_results.append(result)
        
        # If we have results, sort by quality and pick the best
        if all_results:
            # Sort by valid character count and text length
            all_results.sort(key=lambda x: (x['valid_chars'], x['length']), reverse=True)
            best_result = all_results[0]
            
            logger.info(f"Best result from {best_result['technique']} with PSM {best_result['mode']}")
            return best_result['text']
        else:
            return "No text could be extracted from the image."
            
    except Exception as e:
        logger.error(f"Error in text extraction: {str(e)}")
        return f"Error processing image: {str(e)}" 