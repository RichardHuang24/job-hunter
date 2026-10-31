"""Country names and regions -> ISO 3166-1 alpha-2 codes.

Job sources write places their own way ("UK", "United Kingdom", "Congo, The
Democratic Republic of the", "EMEA"). `parse_places` turns such a list into
codes, so the work-permit check can compare them with where a person can
work. Unknown names are skipped, never guessed.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass

# ISO 3166-1 alpha-2, plus XK (Kosovo, widely used though not assigned).
_ISO = """
AD Andorra|AE United Arab Emirates|AF Afghanistan|AG Antigua and Barbuda|AI Anguilla|AL Albania|AM Armenia
AO Angola|AQ Antarctica|AR Argentina|AS American Samoa|AT Austria|AU Australia|AW Aruba|AX Åland Islands
AZ Azerbaijan|BA Bosnia and Herzegovina|BB Barbados|BD Bangladesh|BE Belgium|BF Burkina Faso|BG Bulgaria
BH Bahrain|BI Burundi|BJ Benin|BL Saint Barthélemy|BM Bermuda|BN Brunei|BO Bolivia|BQ Caribbean Netherlands
BR Brazil|BS Bahamas|BT Bhutan|BV Bouvet Island|BW Botswana|BY Belarus|BZ Belize|CA Canada|CC Cocos (Keeling) Islands
CD Democratic Republic of the Congo|CF Central African Republic|CG Republic of the Congo|CH Switzerland
CI Côte d'Ivoire|CK Cook Islands|CL Chile|CM Cameroon|CN China|CO Colombia|CR Costa Rica|CU Cuba|CV Cape Verde
CW Curaçao|CX Christmas Island|CY Cyprus|CZ Czechia|DE Germany|DJ Djibouti|DK Denmark|DM Dominica
DO Dominican Republic|DZ Algeria|EC Ecuador|EE Estonia|EG Egypt|EH Western Sahara|ER Eritrea|ES Spain|ET Ethiopia
FI Finland|FJ Fiji|FK Falkland Islands|FM Micronesia|FO Faroe Islands|FR France|GA Gabon|GB United Kingdom
GD Grenada|GE Georgia|GF French Guiana|GG Guernsey|GH Ghana|GI Gibraltar|GL Greenland|GM Gambia|GN Guinea
GP Guadeloupe|GQ Equatorial Guinea|GR Greece|GS South Georgia and the South Sandwich Islands|GT Guatemala|GU Guam
GW Guinea-Bissau|GY Guyana|HK Hong Kong|HM Heard Island and McDonald Islands|HN Honduras|HR Croatia|HT Haiti
HU Hungary|ID Indonesia|IE Ireland|IL Israel|IM Isle of Man|IN India|IO British Indian Ocean Territory|IQ Iraq
IR Iran|IS Iceland|IT Italy|JE Jersey|JM Jamaica|JO Jordan|JP Japan|KE Kenya|KG Kyrgyzstan|KH Cambodia
KI Kiribati|KM Comoros|KN Saint Kitts and Nevis|KP North Korea|KR South Korea|KW Kuwait|KY Cayman Islands
KZ Kazakhstan|LA Laos|LB Lebanon|LC Saint Lucia|LI Liechtenstein|LK Sri Lanka|LR Liberia|LS Lesotho|LT Lithuania
LU Luxembourg|LV Latvia|LY Libya|MA Morocco|MC Monaco|MD Moldova|ME Montenegro|MF Saint Martin|MG Madagascar
MH Marshall Islands|MK North Macedonia|ML Mali|MM Myanmar|MN Mongolia|MO Macao|MP Northern Mariana Islands
MQ Martinique|MR Mauritania|MS Montserrat|MT Malta|MU Mauritius|MV Maldives|MW Malawi|MX Mexico|MY Malaysia
MZ Mozambique|NA Namibia|NC New Caledonia|NE Niger|NF Norfolk Island|NG Nigeria|NI Nicaragua|NL Netherlands
NO Norway|NP Nepal|NR Nauru|NU Niue|NZ New Zealand|OM Oman|PA Panama|PE Peru|PF French Polynesia
PG Papua New Guinea|PH Philippines|PK Pakistan|PL Poland|PM Saint Pierre and Miquelon|PN Pitcairn Islands
PR Puerto Rico|PS Palestine|PT Portugal|PW Palau|PY Paraguay|QA Qatar|RE Réunion|RO Romania|RS Serbia|RU Russia
RW Rwanda|SA Saudi Arabia|SB Solomon Islands|SC Seychelles|SD Sudan|SE Sweden|SG Singapore|SH Saint Helena
SI Slovenia|SJ Svalbard and Jan Mayen|SK Slovakia|SL Sierra Leone|SM San Marino|SN Senegal|SO Somalia|SR Suriname
SS South Sudan|ST São Tomé and Príncipe|SV El Salvador|SX Sint Maarten|SY Syria|SZ Eswatini
TC Turks and Caicos Islands|TD Chad|TF French Southern Territories|TG Togo|TH Thailand|TJ Tajikistan|TK Tokelau
TL Timor-Leste|TM Turkmenistan|TN Tunisia|TO Tonga|TR Turkey|TT Trinidad and Tobago|TV Tuvalu|TW Taiwan
TZ Tanzania|UA Ukraine|UG Uganda|UM United States Minor Outlying Islands|US United States|UY Uruguay
UZ Uzbekistan|VA Vatican City|VC Saint Vincent and the Grenadines|VE Venezuela|VG British Virgin Islands
VI U.S. Virgin Islands|VN Vietnam|VU Vanuatu|WF Wallis and Futuna|WS Samoa|XK Kosovo|YE Yemen|YT Mayotte
ZA South Africa|ZM Zambia|ZW Zimbabwe
"""

NAMES: dict[str, str] = {}
for _entry in _ISO.replace("\n", "|").split("|"):
    if _entry.strip():
        _code, _name = _entry.strip().split(" ", 1)
        NAMES[_code] = _name

# Other spellings sources use, including ISO's formal "X, Republic of" forms.
_ALIASES = {
    "GB": ["UK", "U.K.", "Great Britain", "Britain", "England", "Scotland", "Wales", "Northern Ireland"],
    "US": ["USA", "U.S.", "U.S.A.", "United States of America", "America"],
    "AE": ["UAE"], "BN": ["Brunei Darussalam"], "BO": ["Bolivia, Plurinational State of"],
    "CD": ["Congo, The Democratic Republic of the", "DR Congo", "DRC", "Congo-Kinshasa"],
    "CG": ["Congo", "Congo-Brazzaville"], "CI": ["Ivory Coast", "Cote d'Ivoire"], "CV": ["Cabo Verde"],
    "CZ": ["Czech Republic"], "FK": ["Falkland Islands (Malvinas)"], "FM": ["Micronesia, Federated States of"],
    "HK": ["Hong Kong SAR"], "IR": ["Iran, Islamic Republic of"], "KP": ["Korea, Democratic People's Republic of"],
    "KR": ["Korea, Republic of", "Korea", "Republic of Korea"], "LA": ["Lao People's Democratic Republic"],
    "MD": ["Moldova, Republic of"], "MK": ["Macedonia", "Republic of North Macedonia"], "MM": ["Burma"],
    "MO": ["Macau"], "NL": ["The Netherlands", "Holland"], "PS": ["Palestine, State of"],
    "RU": ["Russian Federation"], "SY": ["Syrian Arab Republic"], "SZ": ["Swaziland"], "BS": ["The Bahamas"],
    "GM": ["The Gambia"], "TR": ["Türkiye", "Turkiye"], "TW": ["Taiwan, Province of China"],
    "TZ": ["Tanzania, United Republic of"], "VA": ["Holy See", "Holy See (Vatican City State)"],
    "VE": ["Venezuela, Bolivarian Republic of"], "VG": ["Virgin Islands, British"], "VI": ["Virgin Islands, U.S."],
    "VN": ["Viet Nam"], "PN": ["Pitcairn"], "SH": ["Saint Helena, Ascension and Tristan da Cunha"],
    "BQ": ["Bonaire, Sint Eustatius and Saba"], "MF": ["Saint Martin (French part)"], "SX": ["Sint Maarten (Dutch part)"],
    "TL": ["East Timor"], "CN": ["Mainland China"],
}

EU = ("AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO SK SI ES SE").split()
EUROPE = EU + "GB IS LI NO CH AD MC SM VA AL BA ME MK RS XK MD UA".split()
_MIDDLE_EAST = "AE BH EG IL IQ IR JO KW LB OM PS QA SA SY TR YE".split()
_AFRICA = ("DZ AO BJ BW BF BI CM CV CF TD KM CD CG CI DJ ER ET GA GM GH GN GW KE LS LR LY MG MW ML MR MU MA MZ NA "
           "NE NG RW ST SN SC SL SO ZA SS SD SZ TZ TG TN UG ZM ZW").split()
_LATAM = "AR BO BR CL CO CR CU DO EC SV GT HN MX NI PA PY PE PR UY VE".split()
_APAC = "AU BD BN KH CN FJ HK IN ID JP LA MO MY MV MN MM NP NZ PK PG PH SG KR LK TW TH TL VN".split()
_NORTH_AMERICA = ["US", "CA"]

REGIONS: dict[str, list[str]] = {
    "Europe": EUROPE, "European Union": EU, "EU": EU, "EEA": EU + ["IS", "LI", "NO"],
    "EMEA": EUROPE + _MIDDLE_EAST + _AFRICA, "Middle East": _MIDDLE_EAST, "Africa": _AFRICA,
    "LATAM": _LATAM, "Latin America": _LATAM, "South America": "AR BO BR CL CO EC GY PY PE SR UY VE".split(),
    "APAC": _APAC, "Asia Pacific": _APAC, "Asia-Pacific": _APAC, "Asia": [c for c in _APAC if c not in ("AU", "NZ", "FJ", "PG")],
    "North America": _NORTH_AMERICA, "Americas": _NORTH_AMERICA + _LATAM, "Nordics": "DK FI IS NO SE".split(),
    "Oceania": ["AU", "NZ", "FJ", "PG"], "DACH": ["DE", "AT", "CH"], "Benelux": ["BE", "NL", "LU"],
}
WORLDWIDE = {"anywhere", "worldwide", "global", "remote", "world", "international"}


def key(text: str) -> str:
    """'Côte d’Ivoire' -> 'cote d ivoire'"""
    plain = unicodedata.normalize("NFKD", text or "")
    plain = "".join(ch for ch in plain if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", plain.casefold()).strip()


_BY_NAME: dict[str, str] = {}
for _code, _name in NAMES.items():
    _BY_NAME[key(_name)] = _code
for _code, _names in _ALIASES.items():
    for _name in _names:
        _BY_NAME[key(_name)] = _code
_REGIONS_BY_NAME = {key(name): codes for name, codes in REGIONS.items()}


def code_for(name: str) -> str:
    """The ISO code for a country name or code, or "" when it isn't one."""
    text = (name or "").strip()
    if len(text) == 2 and text.upper() in NAMES:
        return text.upper()
    return _BY_NAME.get(key(text), "")


@dataclass(frozen=True)
class Places:
    codes: tuple[str, ...]  # every country named or in a named region, in order
    worldwide: bool  # "Anywhere" and the like
    unknown: tuple[str, ...]  # names that are neither


def parse_places(names: Iterable[str]) -> Places:
    codes: list[str] = []
    unknown: list[str] = []
    worldwide = False
    for raw in names:
        name = (raw or "").strip()
        if not name:
            continue
        if key(name) in WORLDWIDE:
            worldwide = True
        elif code := code_for(name):
            codes.append(code)
        elif region := _REGIONS_BY_NAME.get(key(name)):
            codes.extend(region)
        else:
            unknown.append(name)
    return Places(tuple(dict.fromkeys(codes)), worldwide, tuple(unknown))


def name_for(code: str) -> str:
    return NAMES.get(code, code)
