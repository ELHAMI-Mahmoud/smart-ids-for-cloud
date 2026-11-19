"""Configuration commune du moteur, de la CLI et de Streamlit."""
from dataclasses import asdict, dataclass
import ipaddress
import json
import re

ENGINE_VERSION = '1.0.0'


@dataclass(frozen=True)
class AnalysisConfig:
    lab_cidrs: tuple[str, ...]
    interface_id: str
    port_threshold: int = 20
    byte_threshold: int = 50_000_000
    window_policy: str = 'exclude'
    window_minutes: int = 5
    schema_version: int = 1

    def __post_init__(self):
        if not self.lab_cidrs or isinstance(self.lab_cidrs, str):
            raise ValueError('Indiquer au moins un CIDR du laboratoire.')
        try:
            networks = [ipaddress.ip_network(cidr.strip(), strict=True) for cidr in self.lab_cidrs]
        except (ValueError, AttributeError) as exc:
            raise ValueError('CIDR invalide ; utiliser un réseau aligné ou /32 pour un hôte IPv4.') from exc
        if any(n.prefixlen == 0 for n in networks):
            raise ValueError('Un périmètre /0 ne définit pas un laboratoire.')
        object.__setattr__(self, 'lab_cidrs', tuple(sorted({str(n) for n in networks})))
        if not isinstance(self.interface_id, str) or not re.fullmatch(r'eni-[a-zA-Z0-9]+', self.interface_id):
            raise ValueError('Une interface ENI unique est requise (eni-…).')
        for name in ['port_threshold', 'byte_threshold']:
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= 2**63 - 1:
                raise ValueError(f'{name} doit être un entier strictement positif, borné à int64.')
        if self.port_threshold > 65536:
            raise ValueError('Le seuil de ports ne peut dépasser 65 536 ports distincts.')
        if self.window_policy not in ['exclude', 'end']:
            raise ValueError('Politique temporelle attendue : exclude ou end.')
        if type(self.window_minutes) is not int or self.window_minutes != 5:
            raise ValueError('La V1 utilise uniquement des fenêtres fixes de cinq minutes.')
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError('Version de configuration non prise en charge.')

    def to_dict(self):
        result = asdict(self)
        result['lab_cidrs'] = list(self.lab_cidrs)
        return result

    def canonical_json(self):
        return json.dumps(self.to_dict(), sort_keys=True, separators=(',', ':'), ensure_ascii=False)

    @classmethod
    def from_dict(cls, values):
        if not isinstance(values, dict):
            raise ValueError('Objet JSON de configuration attendu.')
        try:
            return cls(**values)
        except TypeError as exc:
            raise ValueError('Champs de configuration manquants ou inconnus.') from exc
