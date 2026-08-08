from typing import Dict, Any


# ============================================================
# CONFIGURACIÓN DE PONDERACIONES
# ============================================================

CURRENCY_WEIGHTS = {

    # ========================================================
    # USD
    # ========================================================
    "USD": {
        "families": {
            "inflacion": 0.30,
            "empleo": 0.30,
            "actividad": 0.20,
            "demanda": 0.12,
            "sentimiento": 0.08,
        },

        "indicators": {
            "inflacion": {
                "Core CPI YoY": 0.40,
                "CPI YoY": 0.35,
                "Core PPI MoM": 0.15,
                "PPI MoM": 0.10,
            },

            "empleo": {
                "Non Farm Payrolls": 0.35,
                "Unemployment Rate": 0.30,
                "Average Hourly Earnings": 0.25,
                "JOLTS": 0.06,
                "ADP Employment": 0.04,
            },

            "actividad": {
                "GDP Growth Rate (QoQ)": 0.35,
                "ISM Services": 0.30,
                "ISM Manufacturing": 0.25,
                "GDP Annual Growth Rate (YoY)": 0.10,
            },

            "demanda": {
                "Core Retail Sales": 0.55,
                "Retail Sales MoM": 0.45,
            },

            "sentimiento": {
                "Consumer Confidence CB": 1.00,
            },
        },
    },

    # ========================================================
    # EUR
    # ========================================================
    "EUR": {
        "families": {
            "inflacion": 0.50,
            "empleo": 0.12,
            "actividad": 0.20,
            "demanda": 0.10,
            "sentimiento": 0.08,
        },

        "indicators": {
            "inflacion": {
                "Core CPI YoY": 0.40,
                "CPI YoY": 0.35,
                "Core CPI MoM": 0.15,
                "CPI MoM": 0.10,
            },

            "empleo": {
                "Euro Area Wage Growth": 0.65,
                "Unemployment Rate": 0.35,
            },

            "actividad": {
                "GDP Growth Rate (QoQ)": 0.30,
                "Services PMI": 0.25,
                "Manufacturing PMI": 0.20,
                "Industrial Production YoY": 0.15,
                "GDP Annual Growth Rate (YoY)": 0.10,
            },

            "demanda": {
                "Retail Sales MoM": 0.60,
                "Retail Sales YoY": 0.40,
            },

            "sentimiento": {
                "Eurozone Business Climate": 0.40,
                "ZEW Economic Sentiment": 0.35,
                "Consumer Confidence": 0.25,
            },
        },
    },

    # ========================================================
    # GBP
    # ========================================================
    "GBP": {
        "families": {
            "inflacion": 0.45,
            "empleo": 0.25,
            "actividad": 0.15,
            "demanda": 0.08,
            "sentimiento": 0.07,
        },

        "indicators": {
            "inflacion": {
                "Core CPI YoY": 0.40,
                "CPI YoY": 0.35,
                "Core CPI MoM": 0.15,
                "CPI MoM": 0.10,
            },

            "empleo": {
                "Average Earnings (- Bonus)": 0.30,
                "Average Earnings (+ Bonus)": 0.25,
                "Unemployment Rate": 0.25,
                "Employment Change (3M/3M)": 0.20,
            },

            "actividad": {
                "GDP Growth Rate (QoQ)": 0.35,
                "Services PMI": 0.30,
                "Manufacturing PMI": 0.25,
                "GDP Annual Growth Rate (YoY)": 0.10,
            },

            "demanda": {
                "Core Retail Sales": 0.55,
                "Retail Sales MoM": 0.45,
            },

            "sentimiento": {
                "Consumer Confidence": 1.00,
            },
        },
    },

    # ========================================================
    # JPY
    # ========================================================
    "JPY": {
        "families": {
            "inflacion": 0.40,
            "empleo": 0.25,
            "actividad": 0.15,
            "demanda": 0.15,
            "sentimiento": 0.05,
        },

        "indicators": {
            "inflacion": {
                "Core CPI YoY": 0.35,
                "Tokyo CPI YoY": 0.35,
                "CPI YoY": 0.30,
            },

            "empleo": {
                "Average Cash Earnings YoY": 0.55,
                "Unemployment Rate": 0.25,
                "Employment": 0.20,
            },

            "actividad": {
                "GDP Growth Rate (QoQ)": 0.30,
                "Services PMI": 0.25,
                "Manufacturing PMI": 0.25,
                "GDP Annual Growth Rate (YoY)": 0.20,
            },

            "demanda": {
                "Household Spending YoY": 0.60,
                "Retail Sales MoM": 0.40,
            },

            "sentimiento": {
                "Business Confidence": 0.60,
                "Consumer Confidence": 0.40,
            },
        },
    },

    # ========================================================
    # CAD
    # ========================================================
    "CAD": {
        "families": {
            "inflacion": 0.40,
            "empleo": 0.20,
            "actividad": 0.20,
            "demanda": 0.12,
            "sentimiento": 0.08,
        },

        "indicators": {
            "inflacion": {
                "Core CPI YoY": 0.60,
                "CPI YoY": 0.40,
            },

            "empleo": {
                "Employment": 0.55,
                "Unemployment Rate": 0.45,
            },

            "actividad": {
                "GDP Growth Rate (QoQ)": 0.35,
                "Services PMI": 0.25,
                "Manufacturing PMI": 0.25,
                "GDP Annual Growth Rate (YoY)": 0.15,
            },

            "demanda": {
                "Retail Sales MoM": 1.00,
            },

            "sentimiento": {
                "Business Confidence": 0.60,
                "Consumer Confidence": 0.40,
            },
        },
    },

    # ========================================================
    # AUD
    # ========================================================
    "AUD": {
        "families": {
            "inflacion": 0.32,
            "empleo": 0.30,
            "actividad": 0.18,
            "demanda": 0.12,
            "sentimiento": 0.08,
        },

        "indicators": {
            "inflacion": {
                "Core CPI YoY": 0.60,
                "CPI YoY": 0.40,
            },

            "empleo": {
                "Employment": 0.55,
                "Unemployment Rate": 0.45,
            },

            "actividad": {
                "GDP Growth Rate (QoQ)": 0.35,
                "Services PMI": 0.25,
                "Manufacturing PMI": 0.25,
                "GDP Annual Growth Rate (YoY)": 0.15,
            },

            "demanda": {
                "Household Spending MoM": 1.00,
            },

            "sentimiento": {
                "Business Confidence": 0.60,
                "Consumer Confidence": 0.40,
            },
        },
    },

    # ========================================================
    # NZD
    # ========================================================
    "NZD": {
        "families": {
            "inflacion": 0.35,
            "empleo": 0.28,
            "actividad": 0.17,
            "demanda": 0.12,
            "sentimiento": 0.08,
        },

        "indicators": {
            "inflacion": {
                "Core CPI YoY": 0.60,
                "CPI YoY": 0.40,
            },

            "empleo": {
                "Employment": 0.55,
                "Unemployment Rate": 0.45,
            },

            "actividad": {
                "GDP Growth Rate (QoQ)": 0.35,
                "Services PMI": 0.25,
                "Manufacturing PMI": 0.25,
                "GDP Annual Growth Rate (YoY)": 0.15,
            },

            "demanda": {
                "Retail Sales MoM": 1.00,
            },

            "sentimiento": {
                "Business Confidence": 0.60,
                "Consumer Confidence": 0.40,
            },
        },
    },

    # ========================================================
    # CHF
    # ========================================================
    "CHF": {
        "families": {
            "inflacion": 0.55,
            "empleo": 0.08,
            "actividad": 0.20,
            "demanda": 0.09,
            "sentimiento": 0.08,
        },

        "indicators": {
            "inflacion": {
                "Core CPI YoY": 0.60,
                "CPI YoY": 0.40,
            },

            "empleo": {
                "Unemployment Rate": 0.60,
                "Employment": 0.40,
            },

            "actividad": {
                "GDP Growth Rate (QoQ)": 0.35,
                "Services PMI": 0.25,
                "Manufacturing PMI": 0.25,
                "GDP Annual Growth Rate (YoY)": 0.15,
            },

            "demanda": {
                "Retail Sales MoM": 1.00,
            },

            "sentimiento": {
                "Business Confidence": 0.65,
                "Consumer Confidence": 0.35,
            },
        },
    },
}
