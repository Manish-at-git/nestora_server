"""User-facing amenity API messages."""


class AmenityMessage:
    CREATED = "Amenity added successfully"
    STATUS_UPDATED = "Amenity status updated"
    DELETED = "Amenity deleted successfully"
    BOOKED = "Amenity booked successfully"
    FORBIDDEN = "You are not allowed to access this amenity"
    NOT_FOUND = "Amenity not found"
    INACTIVE = "Amenity is currently inactive"
    SLOT_BOOKED = "This time slot is already booked"
    WALLET_NOT_FOUND = "Wallet not found for this account"
    INVALID_PIN = "Invalid wallet security PIN"
    INSUFFICIENT_BALANCE = "Insufficient wallet balance"
    INVALID_ASSOCIATION = "Association is invalid"
    INVALID_TIME = "Booking end time must be after start time"
    INVALID_DURATION = "Booking duration must be greater than zero"

