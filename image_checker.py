import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from datetime import datetime
import os
from dotenv import load_dotenv
from PIL import Image
from io import BytesIO
import time
import base64
import re

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('image_checker.log'),
        logging.StreamHandler()
    ]
)

MIN_WIDTH = 200
MIN_HEIGHT = 200

class ImageChecker:
    def __init__(self):
        self.url = "https://tutor4science.com/"
        self.email_sender = os.getenv('EMAIL_SENDER')
        self.email_password = os.getenv('EMAIL_APP_PASSWORD')
        self.email_receiver = os.getenv('EMAIL_RECEIVER')
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587

        # Validate email configuration
        if not all([self.email_sender, self.email_password, self.email_receiver]):
            raise ValueError("Email configuration is incomplete. Please check your .env file.")

    def is_base64_image(self, img_url):
        return img_url.startswith('data:image')

    def check_image_url(self, img_url):
        try:
            # Skip base64 images as they are embedded in the HTML
            if self.is_base64_image(img_url):
                return True, None, None

            response = requests.get(img_url, timeout=10)
            if response.status_code == 200:
                # Try to open the image to verify it's valid
                img = Image.open(BytesIO(response.content))
                width, height = img.size
                # Only check images larger than the threshold
                if width >= MIN_WIDTH and height >= MIN_HEIGHT:
                    img.verify()
                    return True, width, height
                else:
                    # Ignore small images
                    return None, width, height
            return False, None, None
        except Exception as e:
            logging.error(f"Error checking image {img_url}: {str(e)}")
            return False, None, None

    def send_email_notification(self, broken_images):
        if not broken_images:
            return

        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_sender
            msg['To'] = self.email_receiver
            msg['Subject'] = f"Broken Images Found on {self.url}"

            body = "The following images are not rendering properly (only main content images are checked):\n\n"
            for img, width, height in broken_images:
                body += f"- {img} (size: {width}x{height})\n"
            
            msg.attach(MIMEText(body, 'plain'))

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_sender, self.email_password)
                server.send_message(msg)

            logging.info("Email notification sent successfully")
        except Exception as e:
            logging.error(f"Error sending email: {str(e)}")

    def check_website_images(self):
        try:
            response = requests.get(self.url, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            images = soup.find_all('img')
            
            broken_images = []
            
            for img in images:
                img_url = img.get('src', '')
                if not img_url:
                    continue
                
                # Convert relative URLs to absolute URLs
                if not img_url.startswith(('http://', 'https://', 'data:image')):
                    img_url = requests.compat.urljoin(self.url, img_url)
                
                result, width, height = self.check_image_url(img_url)
                if result is False and width and height and width >= MIN_WIDTH and height >= MIN_HEIGHT:
                    broken_images.append((img_url, width, height))
                    logging.warning(f"Broken main image found: {img_url} (size: {width}x{height})")
                elif result is None:
                    # Small image, ignore
                    continue
            
            if broken_images:
                self.send_email_notification(broken_images)
            else:
                logging.info("All main content images are rendering properly")
                
            return broken_images
            
        except Exception as e:
            logging.error(f"Error checking website: {str(e)}")
            return []

def main():
    try:
        checker = ImageChecker()
        while True:
            logging.info("Starting image check...")
            checker.check_website_images()
            # Wait for 1 hour before next check
            time.sleep(3600)
    except KeyboardInterrupt:
        logging.info("Script stopped by user")
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")

if __name__ == "__main__":
    main() 