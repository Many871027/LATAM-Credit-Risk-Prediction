from typing import Tuple

def calculate_credit_decision(pd: float, income: float) -> Tuple[float, str]:
    """
    Calculates the dynamic credit limit and decision based on the Probability of Default (PD)
    and user monthly income using the piecewise risk policy:
    
    1. IF PD > 0.10 (High Risk), return credit limit = 0.0 and decision = "REJECT".
    2. IF 0.04 < PD <= 0.10 (Medium Risk), return credit limit = min(max(0.10 * income, 2000.0), 25000.0) 
       and decision = "APPROVE_MEDIUM_RISK".
    3. IF PD <= 0.04 (Low Risk), return credit limit = min(max(0.25 * income, 5000.0), 100000.0)
       and decision = "APPROVE_LOW_RISK".
    """
    if pd > 0.10:
        return 0.0, "REJECT"
    elif pd > 0.04:
        credit_limit = min(max(0.10 * income, 2000.0), 25000.0)
        return float(credit_limit), "APPROVE_MEDIUM_RISK"
    else:
        credit_limit = min(max(0.25 * income, 5000.0), 100000.0)
        return float(credit_limit), "APPROVE_LOW_RISK"
