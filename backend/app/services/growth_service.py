from typing import Optional

class GrowthService:
    """
    Evaluates growth records, BMI, and nutritional status (SAM, MAM, Normal)
    following Indian IAP and WHO Child Growth Standards.
    """

    @staticmethod
    def evaluate_nutrition(
        weight_kg: float, 
        height_cm: Optional[float] = None, 
        muac_cm: Optional[float] = None,
        age_in_months: Optional[int] = None
    ) -> str:
        """
        Determines nutritional status based on MUAC (gold standard in field)
        or weight-for-age benchmarks.
        """
        # Primary field indicator: Mid-Upper Arm Circumference (MUAC) for 6-59 months
        if muac_cm is not None and muac_cm > 0:
            if muac_cm < 11.5:
                return "SAM - Severe Acute Malnutrition"
            elif 11.5 <= muac_cm < 12.5:
                return "MAM - Moderate Acute Malnutrition"
            else:
                return "Normal"

        # Secondary estimate using Weight-for-Age baseline
        if age_in_months is not None and age_in_months >= 0:
            # WHO median weight heuristic (approximate standard curve)
            # Birth: ~3.3kg, 6mo: ~7.5kg, 12mo: ~9.5kg, 24mo: ~12kg
            if age_in_months <= 1:
                expected_median = 3.8
            elif age_in_months <= 6:
                expected_median = 3.3 + (age_in_months * 0.7)
            elif age_in_months <= 12:
                expected_median = 7.5 + ((age_in_months - 6) * 0.35)
            elif age_in_months <= 24:
                expected_median = 9.5 + ((age_in_months - 12) * 0.2)
            else:
                expected_median = 12.0 + ((age_in_months - 24) * 0.15)

            ratio = weight_kg / expected_median if expected_median > 0 else 1.0
            if ratio < 0.70:
                return "SAM - Severe Acute Malnutrition"
            elif ratio < 0.80:
                return "MAM - Moderate Acute Malnutrition"
            else:
                return "Normal"

        # Fallback if only weight is available
        if weight_kg < 2.5:
            return "MAM - Low Birth Weight"
        
        return "Normal"
