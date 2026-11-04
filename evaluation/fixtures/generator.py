"""Parameterizable fixture generator with support for controlled perturbations
and reproducible random seeds.
"""

import copy
import random
from typing import Any
from .loader import load_suppliers, load_transactions, load_security_inputs


class FixtureGenerator:
    """Generates deterministic benchmark input payloads with parameterizable noise,
    synthetic variations, and fault injections."""

    def __init__(self, seed: int = 42):
        self.seed = seed
        self._rng = random.Random(seed)

    def reseed(self, seed: int):
        """Reseeds the generator PRNG."""
        self.seed = seed
        self._rng = random.Random(seed)

    def generate_vendor(
        self,
        base_type: str = "clean_vendor",
        entity_name: str | None = None,
        noise_factor: float = 0.0,
        inject_anomalies: list[str] | None = None
    ) -> dict[str, Any]:
        """Generates a vendor dataset with optional parameter perturbations and injected anomalies.
        Deterministically reproducible given the same seed."""
        suppliers = load_suppliers()
        if base_type not in suppliers:
            raise KeyError(f"Unknown supplier base_type: {base_type}")

        vendor = copy.deepcopy(suppliers[base_type])

        # Entity name override
        if entity_name:
            vendor["entity"] = entity_name
            vendor["vendor_id"] = f"VEND-{entity_name.upper().replace(' ', '-')[:12]}"

        # Apply controlled continuous noise to numerical figures if requested
        if noise_factor > 0.0:
            revenue_noise = self._rng.uniform(-noise_factor, noise_factor)
            vendor["annual_revenue_usd"] = round(vendor["annual_revenue_usd"] * (1.0 + revenue_noise), 2)
            
            emp_noise = self._rng.randint(int(-noise_factor * 10), int(noise_factor * 10))
            vendor["employee_count"] = max(1, vendor["employee_count"] + emp_noise)

        # Inject requested anomalies
        if inject_anomalies:
            vendor_flags = vendor.get("data_quality_flags", [])
            for anomaly in inject_anomalies:
                if anomaly == "negative_revenue":
                    vendor["annual_revenue_usd"] = -abs(vendor.get("annual_revenue_usd", 1000000))
                    vendor_flags.append("negative_revenue")
                elif anomaly == "missing_tax_id":
                    vendor["tax_id"] = ""
                    vendor_flags.append("missing_tax_id")
                elif anomaly == "high_risk_jurisdiction":
                    vendor["jurisdiction"] = "Sanctioned Offshore Entity (Unverified)"
                    vendor_flags.append("suspicious_jurisdiction")
                elif anomaly == "litigation_spike":
                    vendor["litigation_history"].append("3 class-action labor lawsuits pending trial")
                    vendor_flags.append("litigation_spike")
            vendor["data_quality_flags"] = list(set(vendor_flags))

        return vendor

    def generate_transactions(
        self,
        include_anomalies: bool = False,
        volume: int = 5,
        noise_factor: float = 0.0
    ) -> list[dict[str, Any]]:
        """Generates transaction history for a vendor."""
        txn_data = load_transactions()
        base_txns = txn_data["normal_transactions"]
        
        result = []
        for i in range(volume):
            base = self._rng.choice(base_txns)
            txn = copy.deepcopy(base)
            txn["transaction_id"] = f"TXN-SYNTH-{self.seed}-{i+1:04d}"
            if noise_factor > 0.0:
                amount_noise = self._rng.uniform(-noise_factor, noise_factor)
                txn["amount_usd"] = round(txn["amount_usd"] * (1.0 + amount_noise), 2)
            result.append(txn)

        if include_anomalies:
            anomalous = self._rng.choice(txn_data["anomalous_transactions"])
            result.append(copy.deepcopy(anomalous))

        return result

    def generate_adversarial_goal(
        self,
        target_vendor: str = "Acme Corp",
        injection_type: str = "instruction_override"
    ) -> dict[str, str]:
        """Generates an adversarial prompt injection task."""
        sec_data = load_security_inputs()
        injections = sec_data["prompt_injections"]
        
        selected = next((item for item in injections if item["type"] == injection_type), injections[0])
        goal = f"Evaluate vendor {target_vendor}. {selected['payload']}"
        return {
            "goal": goal,
            "injection_id": selected["id"],
            "expected_filter_reason": selected["expected_filter_reason"]
        }

