import time
import socket
import ssl
import logging
import requests
from datetime import datetime
from urllib.parse import urlparse
from django.utils import timezone
from .models import Website, WebsiteCheck

logger = logging.getLogger("WebsiteChecker")


def get_ssl_expiry(url):
    """
    Connects to the hostname on port 443 via raw socket, wraps with SSL context,
    gathers the peer certificate, and extracts the expiration date.
    Returns: (expiry_date, is_valid)
    """
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return None, False

        # Only check SSL for HTTPS schemes
        if parsed.scheme != 'https':
            return None, True

        port = parsed.port or 443
        context = ssl.create_default_context()
        
        # Set socket connection timeout to 4 seconds
        with socket.create_connection((hostname, port), timeout=4) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                not_after_str = cert.get('notAfter')
                if not_after_str:
                    # Parse certificate date format (e.g. 'May  8 12:00:00 2026 GMT')
                    ssl_expiry = datetime.strptime(not_after_str, '%b %d %H:%M:%S %Y %Z').date()
                    is_valid = ssl_expiry > datetime.now().date()
                    return ssl_expiry, is_valid
                    
    except Exception as e:
        logger.warning(f"SSL check failed for {url}: {e}")
        return None, False
        
    return None, False


def check_website(website):
    """
    Probes a website and logs a WebsiteCheck result in the database.
    Catches timeouts, DNS/connection errors, and SSL handshake exceptions.
    """
    start_time = time.time()
    status = "Online"
    http_status = None
    response_time = None
    redirected = False
    redirect_url = None
    
    # 1. Fetch SSL Expiry info
    ssl_expiry, ssl_valid = get_ssl_expiry(website.url)

    # 2. Probe HTTP Endpoint
    try:
        # Perform HTTP GET request (Timeout at 10s)
        response = requests.get(website.url, timeout=10)
        
        # Calculate wall time in milliseconds
        response_time = (time.time() - start_time) * 1000
        http_status = response.status_code
        
        # Check if redirected
        if len(response.history) > 0:
            redirected = True
            redirect_url = response.url

        # Check if HTTP status is an error, but still "Online" from network standpoint
        status = "Online"

    except requests.exceptions.Timeout:
        status = "Offline"
    except requests.exceptions.SSLError:
        status = "SSL Error"
        ssl_valid = False
    except requests.exceptions.ConnectionError:
        # Captures DNS failures, port connection rejections
        status = "DNS Error"
    except Exception as e:
        logger.error(f"Unexpected error checking {website.url}: {e}")
        status = "Offline"

    # Save to database
    check_result = WebsiteCheck.objects.create(
        website=website,
        status=status,
        http_status=http_status,
        response_time=response_time,
        ssl_expiry=ssl_expiry,
        ssl_valid=ssl_valid,
        redirected=redirected,
        redirect_url=redirect_url,
        checked_at=timezone.now()
    )
    
    speed_str = f"{response_time:.1f}ms" if response_time is not None else "N/A"
    logger.info(f"Checked website {website.name} ({website.url}) -> Status: {status}, HTTP: {http_status}, Speed: {speed_str}")
    return check_result
