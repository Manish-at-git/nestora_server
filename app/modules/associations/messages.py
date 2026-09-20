"""Messages used by association management."""


class AssociationMessage:
    NOT_FOUND = "Association not found"
    FORBIDDEN = "Association access denied"
    SUBSCRIPTION_UPDATED = "Association subscription updated successfully"
    INVALID_WORKBOOK = "Invalid onboarding Excel file"
    WORKBOOK_SHEETS_REQUIRED = "Excel file must contain Association Details, Unit Details, and Homeowner Details sheets"
    ASSOCIATION_SHEET_EMPTY = "Association details sheet is empty"
    INVALID_UNIT_REFERENCE = "A homeowner references a unit that does not exist in the Unit Details sheet"
    ENTITY_NOT_FOUND = "Organization entity not found"
    PLAN_NOT_FOUND = "Subscription plan not found"
