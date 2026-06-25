"""
NUBAN (Nigerian Uniform Bank Account Number) and BVN validator helper functions.
NUBAN algorithm is defined by the Central Bank of Nigeria (CBN).
"""

import hashlib

# Standard weights for the CBN NUBAN check digit algorithm
NUBAN_WEIGHTS = [3, 7, 3, 3, 7, 3, 3, 7, 3, 3, 7, 3]

# Popular Nigerian Banks and their CBN codes
NIGERIAN_BANKS = {
    "011": "First Bank of Nigeria",
    "032": "Union Bank of Nigeria",
    "033": "United Bank for Africa (UBA)",
    "035": "Wema Bank",
    "044": "Access Bank",
    "050": "Ecobank Nigeria",
    "057": "Zenith Bank",
    "058": "Guaranty Trust Bank (GTBank)",
    "070": "Fidelity Bank",
    "214": "First City Monument Bank (FCMB)",
    "215": "Unity Bank",
    "221": "Heritage Bank",
    "232": "Sterling Bank",
    "301": "Jaiz Bank",
    "076": "Polaris Bank",
    "101": "Providus Bank",
}

def validate_nuban(account_number: str, bank_code: str) -> bool:
    """
    Validates a Nigerian bank account number (NUBAN) against its bank code
    using the CBN approved check digit algorithm.
    """
    if not account_number or len(account_number) != 10 or not account_number.isdigit():
        return False
    if not bank_code or len(bank_code) != 3 or not bank_code.isdigit():
        return False

    # Combine Bank Code (3 digits) and Account Serial Number (first 9 digits of account number)
    combined = bank_code + account_number[:9]
    
    # Calculate sum of products
    total_sum = 0
    for digit_char, weight in zip(combined, NUBAN_WEIGHTS):
        total_sum += int(digit_char) * weight
        
    modulo_val = total_sum % 10
    check_digit = 0 if modulo_val == 0 else 10 - modulo_val
    
    # Compare with the 10th digit of the account number
    return check_digit == int(account_number[9])

def validate_bvn(bvn: str) -> bool:
    """
    Validates BVN format (Bank Verification Number must be exactly 11 digits).
    """
    return bool(bvn and len(bvn) == 11 and bvn.isdigit())

def hash_bvn(bvn: str) -> str:
    """
    Hashes BVN to ensure compliance with NDPR (Nigeria Data Protection Regulation).
    Never store raw BVN.
    """
    if not validate_bvn(bvn):
        raise ValueError("Invalid BVN format. Cannot hash.")
    return hashlib.sha256(bvn.encode("utf-8")).hexdigest()
