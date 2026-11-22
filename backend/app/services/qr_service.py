import io
import base64
import qrcode
from qrcode.image.styledpil import StyledPilImage
from app.config import settings

def generate_seat_qr_url(bus_id: int, seat_number: str) -> str:
    """
    Returns the public URL that a passenger scans on the physical bus seat.
    """
    return f"{settings.BASE_URL}/pages/book-seat.html?bus_id={bus_id}&seat={seat_number}"

def generate_qr_image_base64(payload: str) -> str:
    """
    Generates a crisp QR code for the given text payload and returns a Base64 PNG data URL.
    """
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=3,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="#0b1329", back_color="#ffffff")
    
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    b64_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64_str}"

def generate_seat_qr_base64(bus_id: int, seat_number: str) -> str:
    url = generate_seat_qr_url(bus_id, seat_number)
    return generate_qr_image_base64(url)

def generate_ticket_qr_base64(ticket_token: str, booking_ref: str) -> str:
    payload = f"TRAKO:TICKET:{ticket_token}:{booking_ref}"
    return generate_qr_image_base64(payload)
