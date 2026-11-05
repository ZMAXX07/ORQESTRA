/**
 * ISO 4217 Currency Registry and Formatting Utilities
 *
 * Provides a maintained registry of active world currencies, ISO 4217 codes,
 * official display names, symbols, decimal precision, and locale-aware formatters.
 */

export interface CurrencyInfo {
  code: string;
  name: string;
  symbol: string;
  decimals: number;
  label: string;
}

/**
 * Authoritative registry of active ISO 4217 world currencies.
 * Excludes obsolete/demonetized currencies and non-currency test codes (XAU, XAG, etc.).
 */
export const ISO_CURRENCIES: CurrencyInfo[] = [
  { code: 'AED', name: 'UAE Dirham', symbol: 'د.إ', decimals: 2, label: 'AED - UAE Dirham (د.إ)' },
  { code: 'AFN', name: 'Afghan Afghani', symbol: '؋', decimals: 2, label: 'AFN - Afghan Afghani (؋)' },
  { code: 'ALL', name: 'Albanian Lek', symbol: 'L', decimals: 2, label: 'ALL - Albanian Lek (L)' },
  { code: 'AMD', name: 'Armenian Dram', symbol: '֏', decimals: 2, label: 'AMD - Armenian Dram (֏)' },
  { code: 'ANG', name: 'Netherlands Antillean Guilder', symbol: 'ƒ', decimals: 2, label: 'ANG - Netherlands Antillean Guilder (ƒ)' },
  { code: 'AOA', name: 'Angolan Kwanza', symbol: 'Kz', decimals: 2, label: 'AOA - Angolan Kwanza (Kz)' },
  { code: 'ARS', name: 'Argentine Peso', symbol: '$', decimals: 2, label: 'ARS - Argentine Peso ($)' },
  { code: 'AUD', name: 'Australian Dollar', symbol: 'A$', decimals: 2, label: 'AUD - Australian Dollar (A$)' },
  { code: 'AWG', name: 'Aruban Florin', symbol: 'ƒ', decimals: 2, label: 'AWG - Aruban Florin (ƒ)' },
  { code: 'AZN', name: 'Azerbaijani Manat', symbol: '₼', decimals: 2, label: 'AZN - Azerbaijani Manat (₼)' },
  { code: 'BAM', name: 'Bosnia-Herzegovina Convertible Mark', symbol: 'KM', decimals: 2, label: 'BAM - Bosnia-Herzegovina Convertible Mark (KM)' },
  { code: 'BBD', name: 'Barbadian Dollar', symbol: '$', decimals: 2, label: 'BBD - Barbadian Dollar ($)' },
  { code: 'BDT', name: 'Bangladeshi Taka', symbol: '৳', decimals: 2, label: 'BDT - Bangladeshi Taka (৳)' },
  { code: 'BGN', name: 'Bulgarian Lev', symbol: 'лв', decimals: 2, label: 'BGN - Bulgarian Lev (лв)' },
  { code: 'BHD', name: 'Bahraini Dinar', symbol: 'د.ب', decimals: 3, label: 'BHD - Bahraini Dinar (د.ب)' },
  { code: 'BIF', name: 'Burundian Franc', symbol: 'Fr', decimals: 0, label: 'BIF - Burundian Franc (Fr)' },
  { code: 'BMD', name: 'Bermudan Dollar', symbol: '$', decimals: 2, label: 'BMD - Bermudan Dollar ($)' },
  { code: 'BND', name: 'Brunei Dollar', symbol: '$', decimals: 2, label: 'BND - Brunei Dollar ($)' },
  { code: 'BOB', name: 'Bolivian Boliviano', symbol: 'Bs.', decimals: 2, label: 'BOB - Bolivian Boliviano (Bs.)' },
  { code: 'BRL', name: 'Brazilian Real', symbol: 'R$', decimals: 2, label: 'BRL - Brazilian Real (R$)' },
  { code: 'BSD', name: 'Bahamian Dollar', symbol: '$', decimals: 2, label: 'BSD - Bahamian Dollar ($)' },
  { code: 'BTN', name: 'Bhutanese Ngultrum', symbol: 'Nu.', decimals: 2, label: 'BTN - Bhutanese Ngultrum (Nu.)' },
  { code: 'BWP', name: 'Botswanan Pula', symbol: 'P', decimals: 2, label: 'BWP - Botswanan Pula (P)' },
  { code: 'BYN', name: 'Belarusian Ruble', symbol: 'Br', decimals: 2, label: 'BYN - Belarusian Ruble (Br)' },
  { code: 'BZD', name: 'Belize Dollar', symbol: '$', decimals: 2, label: 'BZD - Belize Dollar ($)' },
  { code: 'CAD', name: 'Canadian Dollar', symbol: 'C$', decimals: 2, label: 'CAD - Canadian Dollar (C$)' },
  { code: 'CDF', name: 'Congolese Franc', symbol: 'Fr', decimals: 2, label: 'CDF - Congolese Franc (Fr)' },
  { code: 'CHF', name: 'Swiss Franc', symbol: 'CHF', decimals: 2, label: 'CHF - Swiss Franc (CHF)' },
  { code: 'CLP', name: 'Chilean Peso', symbol: '$', decimals: 0, label: 'CLP - Chilean Peso ($)' },
  { code: 'CNY', name: 'Chinese Yuan', symbol: '¥', decimals: 2, label: 'CNY - Chinese Yuan (¥)' },
  { code: 'COP', name: 'Colombian Peso', symbol: '$', decimals: 2, label: 'COP - Colombian Peso ($)' },
  { code: 'CRC', name: 'Costa Rican Colón', symbol: '₡', decimals: 2, label: 'CRC - Costa Rican Colón (₡)' },
  { code: 'CUP', name: 'Cuban Peso', symbol: '$', decimals: 2, label: 'CUP - Cuban Peso ($)' },
  { code: 'CVE', name: 'Cape Verdean Escudo', symbol: '$', decimals: 2, label: 'CVE - Cape Verdean Escudo ($)' },
  { code: 'CZK', name: 'Czech Koruna', symbol: 'Kč', decimals: 2, label: 'CZK - Czech Koruna (Kč)' },
  { code: 'DJF', name: 'Djiboutian Franc', symbol: 'Fr', decimals: 0, label: 'DJF - Djiboutian Franc (Fr)' },
  { code: 'DKK', name: 'Danish Krone', symbol: 'kr', decimals: 2, label: 'DKK - Danish Krone (kr)' },
  { code: 'DOP', name: 'Dominican Peso', symbol: '$', decimals: 2, label: 'DOP - Dominican Peso ($)' },
  { code: 'DZD', name: 'Algerian Dinar', symbol: 'د.ج', decimals: 2, label: 'DZD - Algerian Dinar (د.ج)' },
  { code: 'EGP', name: 'Egyptian Pound', symbol: 'E£', decimals: 2, label: 'EGP - Egyptian Pound (E£)' },
  { code: 'ERN', name: 'Eritrean Nakfa', symbol: 'Nfk', decimals: 2, label: 'ERN - Eritrean Nakfa (Nfk)' },
  { code: 'ETB', name: 'Ethiopian Birr', symbol: 'Br', decimals: 2, label: 'ETB - Ethiopian Birr (Br)' },
  { code: 'EUR', name: 'Euro', symbol: '€', decimals: 2, label: 'EUR - Euro (€)' },
  { code: 'FJD', name: 'Fijian Dollar', symbol: '$', decimals: 2, label: 'FJD - Fijian Dollar ($)' },
  { code: 'FKP', name: 'Falkland Islands Pound', symbol: '£', decimals: 2, label: 'FKP - Falkland Islands Pound (£)' },
  { code: 'GBP', name: 'Pound Sterling', symbol: '£', decimals: 2, label: 'GBP - Pound Sterling (£)' },
  { code: 'GEL', name: 'Georgian Lari', symbol: '₾', decimals: 2, label: 'GEL - Georgian Lari (₾)' },
  { code: 'GHS', name: 'Ghanaian Cedi', symbol: '₵', decimals: 2, label: 'GHS - Ghanaian Cedi (₵)' },
  { code: 'GIP', name: 'Gibraltar Pound', symbol: '£', decimals: 2, label: 'GIP - Gibraltar Pound (£)' },
  { code: 'GMD', name: 'Gambian Dalasi', symbol: 'D', decimals: 2, label: 'GMD - Gambian Dalasi (D)' },
  { code: 'GNF', name: 'Guinean Franc', symbol: 'Fr', decimals: 0, label: 'GNF - Guinean Franc (Fr)' },
  { code: 'GTQ', name: 'Guatemalan Quetzal', symbol: 'Q', decimals: 2, label: 'GTQ - Guatemalan Quetzal (Q)' },
  { code: 'GYD', name: 'Guyanaese Dollar', symbol: '$', decimals: 2, label: 'GYD - Guyanaese Dollar ($)' },
  { code: 'HKD', name: 'Hong Kong Dollar', symbol: 'HK$', decimals: 2, label: 'HKD - Hong Kong Dollar (HK$)' },
  { code: 'HNL', name: 'Honduran Lempira', symbol: 'L', decimals: 2, label: 'HNL - Honduran Lempira (L)' },
  { code: 'HRK', name: 'Croatian Kuna', symbol: 'kn', decimals: 2, label: 'HRK - Croatian Kuna (kn)' },
  { code: 'HTG', name: 'Haitian Gourde', symbol: 'G', decimals: 2, label: 'HTG - Haitian Gourde (G)' },
  { code: 'HUF', name: 'Hungarian Forint', symbol: 'Ft', decimals: 2, label: 'HUF - Hungarian Forint (Ft)' },
  { code: 'IDR', name: 'Indonesian Rupiah', symbol: 'Rp', decimals: 2, label: 'IDR - Indonesian Rupiah (Rp)' },
  { code: 'ILS', name: 'Israeli New Shekel', symbol: '₪', decimals: 2, label: 'ILS - Israeli New Shekel (₪)' },
  { code: 'INR', name: 'Indian Rupee', symbol: '₹', decimals: 2, label: 'INR - Indian Rupee (₹)' },
  { code: 'IQD', name: 'Iraqi Dinar', symbol: 'ع.د', decimals: 3, label: 'IQD - Iraqi Dinar (ع.د)' },
  { code: 'IRR', name: 'Iranian Rial', symbol: '﷼', decimals: 2, label: 'IRR - Iranian Rial (﷼)' },
  { code: 'ISK', name: 'Icelandic Króna', symbol: 'kr', decimals: 0, label: 'ISK - Icelandic Króna (kr)' },
  { code: 'JMD', name: 'Jamaican Dollar', symbol: '$', decimals: 2, label: 'JMD - Jamaican Dollar ($)' },
  { code: 'JOD', name: 'Jordanian Dinar', symbol: 'د.ا', decimals: 3, label: 'JOD - Jordanian Dinar (د.ا)' },
  { code: 'JPY', name: 'Japanese Yen', symbol: '¥', decimals: 0, label: 'JPY - Japanese Yen (¥)' },
  { code: 'KES', name: 'Kenyan Shilling', symbol: 'KSh', decimals: 2, label: 'KES - Kenyan Shilling (KSh)' },
  { code: 'KGS', name: 'Kyrgystani Som', symbol: 'сом', decimals: 2, label: 'KGS - Kyrgystani Som (сом)' },
  { code: 'KHR', name: 'Cambodian Riel', symbol: '៛', decimals: 2, label: 'KHR - Cambodian Riel (៛)' },
  { code: 'KMF', name: 'Comorian Franc', symbol: 'Fr', decimals: 0, label: 'KMF - Comorian Franc (Fr)' },
  { code: 'KRW', name: 'South Korean Won', symbol: '₩', decimals: 0, label: 'KRW - South Korean Won (₩)' },
  { code: 'KWD', name: 'Kuwaiti Dinar', symbol: 'د.ك', decimals: 3, label: 'KWD - Kuwaiti Dinar (د.ك)' },
  { code: 'KYD', name: 'Cayman Islands Dollar', symbol: '$', decimals: 2, label: 'KYD - Cayman Islands Dollar ($)' },
  { code: 'KZT', name: 'Kazakhstani Tenge', symbol: '₸', decimals: 2, label: 'KZT - Kazakhstani Tenge (₸)' },
  { code: 'LAK', name: 'Laotian Kip', symbol: '₭', decimals: 2, label: 'LAK - Laotian Kip (₭)' },
  { code: 'LBP', name: 'Lebanese Pound', symbol: 'ل.ل', decimals: 2, label: 'LBP - Lebanese Pound (ل.ل)' },
  { code: 'LKR', name: 'Sri Lankan Rupee', symbol: 'Rs', decimals: 2, label: 'LKR - Sri Lankan Rupee (Rs)' },
  { code: 'LRD', name: 'Liberian Dollar', symbol: '$', decimals: 2, label: 'LRD - Liberian Dollar ($)' },
  { code: 'LSL', name: 'Lesotho Loti', symbol: 'L', decimals: 2, label: 'LSL - Lesotho Loti (L)' },
  { code: 'LYD', name: 'Libyan Dinar', symbol: 'د.ل', decimals: 3, label: 'LYD - Libyan Dinar (د.ل)' },
  { code: 'MAD', name: 'Moroccan Dirham', symbol: 'د.م.', decimals: 2, label: 'MAD - Moroccan Dirham (د.م.)' },
  { code: 'MDL', name: 'Moldovan Leu', symbol: 'L', decimals: 2, label: 'MDL - Moldovan Leu (L)' },
  { code: 'MGA', name: 'Malagasy Ariary', symbol: 'Ar', decimals: 2, label: 'MGA - Malagasy Ariary (Ar)' },
  { code: 'MKD', name: 'Macedonian Denar', symbol: 'ден', decimals: 2, label: 'MKD - Macedonian Denar (ден)' },
  { code: 'MMK', name: 'Myanmar Kyat', symbol: 'K', decimals: 2, label: 'MMK - Myanmar Kyat (K)' },
  { code: 'MNT', name: 'Mongolian Tugrik', symbol: '₮', decimals: 2, label: 'MNT - Mongolian Tugrik (₮)' },
  { code: 'MOP', name: 'Macanese Pataca', symbol: 'MOP$', decimals: 2, label: 'MOP - Macanese Pataca (MOP$)' },
  { code: 'MRU', name: 'Mauritanian Ouguiya', symbol: 'UM', decimals: 2, label: 'MRU - Mauritanian Ouguiya (UM)' },
  { code: 'MUR', name: 'Mauritian Rupee', symbol: '₨', decimals: 2, label: 'MUR - Mauritian Rupee (₨)' },
  { code: 'MVR', name: 'Maldivian Rufiyaa', symbol: 'Rf', decimals: 2, label: 'MVR - Maldivian Rufiyaa (Rf)' },
  { code: 'MWK', name: 'Malawian Kwacha', symbol: 'MK', decimals: 2, label: 'MWK - Malawian Kwacha (MK)' },
  { code: 'MXN', name: 'Mexican Peso', symbol: '$', decimals: 2, label: 'MXN - Mexican Peso ($)' },
  { code: 'MYR', name: 'Malaysian Ringgit', symbol: 'RM', decimals: 2, label: 'MYR - Malaysian Ringgit (RM)' },
  { code: 'MZN', name: 'Mozambican Metical', symbol: 'MT', decimals: 2, label: 'MZN - Mozambican Metical (MT)' },
  { code: 'NAD', name: 'Namibian Dollar', symbol: '$', decimals: 2, label: 'NAD - Namibian Dollar ($)' },
  { code: 'NGN', name: 'Nigerian Naira', symbol: '₦', decimals: 2, label: 'NGN - Nigerian Naira (₦)' },
  { code: 'NIO', name: 'Nicaraguan Córdoba', symbol: 'C$', decimals: 2, label: 'NIO - Nicaraguan Córdoba (C$)' },
  { code: 'NOK', name: 'Norwegian Krone', symbol: 'kr', decimals: 2, label: 'NOK - Norwegian Krone (kr)' },
  { code: 'NPR', name: 'Nepalese Rupee', symbol: 'Rs', decimals: 2, label: 'NPR - Nepalese Rupee (Rs)' },
  { code: 'NZD', name: 'New Zealand Dollar', symbol: 'NZ$', decimals: 2, label: 'NZD - New Zealand Dollar (NZ$)' },
  { code: 'OMR', name: 'Omani Rial', symbol: 'ر.ع.', decimals: 3, label: 'OMR - Omani Rial (ر.ع.)' },
  { code: 'PAB', name: 'Panamanian Balboa', symbol: 'B/.', decimals: 2, label: 'PAB - Panamanian Balboa (B/.)' },
  { code: 'PEN', name: 'Peruvian Sol', symbol: 'S/.', decimals: 2, label: 'PEN - Peruvian Sol (S/.)' },
  { code: 'PGK', name: 'Papua New Guinean Kina', symbol: 'K', decimals: 2, label: 'PGK - Papua New Guinean Kina (K)' },
  { code: 'PHP', name: 'Philippine Peso', symbol: '₱', decimals: 2, label: 'PHP - Philippine Peso (₱)' },
  { code: 'PKR', name: 'Pakistani Rupee', symbol: '₨', decimals: 2, label: 'PKR - Pakistani Rupee (₨)' },
  { code: 'PLN', name: 'Polish Złoty', symbol: 'zł', decimals: 2, label: 'PLN - Polish Złoty (zł)' },
  { code: 'PYG', name: 'Paraguayan Guarani', symbol: '₲', decimals: 0, label: 'PYG - Paraguayan Guarani (₲)' },
  { code: 'QAR', name: 'Qatari Riyal', symbol: 'ر.ق', decimals: 2, label: 'QAR - Qatari Riyal (ر.ق)' },
  { code: 'RON', name: 'Romanian Leu', symbol: 'lei', decimals: 2, label: 'RON - Romanian Leu (lei)' },
  { code: 'RSD', name: 'Serbian Dinar', symbol: 'дин.', decimals: 2, label: 'RSD - Serbian Dinar (дин.)' },
  { code: 'RWF', name: 'Rwandan Franc', symbol: 'Fr', decimals: 0, label: 'RWF - Rwandan Franc (Fr)' },
  { code: 'SAR', name: 'Saudi Riyal', symbol: 'ر.س', decimals: 2, label: 'SAR - Saudi Riyal (ر.س)' },
  { code: 'SBD', name: 'Solomon Islands Dollar', symbol: '$', decimals: 2, label: 'SBD - Solomon Islands Dollar ($)' },
  { code: 'SCR', name: 'Seychellois Rupee', symbol: '₨', decimals: 2, label: 'SCR - Seychellois Rupee (₨)' },
  { code: 'SDG', name: 'Sudanese Pound', symbol: 'ج.س.', decimals: 2, label: 'SDG - Sudanese Pound (ج.س.)' },
  { code: 'SEK', name: 'Swedish Krona', symbol: 'kr', decimals: 2, label: 'SEK - Swedish Krona (kr)' },
  { code: 'SGD', name: 'Singapore Dollar', symbol: 'S$', decimals: 2, label: 'SGD - Singapore Dollar (S$)' },
  { code: 'SHP', name: 'Saint Helena Pound', symbol: '£', decimals: 2, label: 'SHP - Saint Helena Pound (£)' },
  { code: 'SLL', name: 'Sierra Leonean Leone', symbol: 'Le', decimals: 2, label: 'SLL - Sierra Leonean Leone (Le)' },
  { code: 'SOS', name: 'Somali Shilling', symbol: 'S', decimals: 2, label: 'SOS - Somali Shilling (S)' },
  { code: 'SRD', name: 'Surinamese Dollar', symbol: '$', decimals: 2, label: 'SRD - Surinamese Dollar ($)' },
  { code: 'SSP', name: 'South Sudanese Pound', symbol: '£', decimals: 2, label: 'SSP - South Sudanese Pound (£)' },
  { code: 'STN', name: 'São Tomé & Príncipe Dobra', symbol: 'Db', decimals: 2, label: 'STN - São Tomé & Príncipe Dobra (Db)' },
  { code: 'SYP', name: 'Syrian Pound', symbol: '£', decimals: 2, label: 'SYP - Syrian Pound (£)' },
  { code: 'SZL', name: 'Swazi Lilangeni', symbol: 'L', decimals: 2, label: 'SZL - Swazi Lilangeni (L)' },
  { code: 'THB', name: 'Thai Baht', symbol: '฿', decimals: 2, label: 'THB - Thai Baht (฿)' },
  { code: 'TJS', name: 'Tajikistani Somoni', symbol: 'SM', decimals: 2, label: 'TJS - Tajikistani Somoni (SM)' },
  { code: 'TMT', name: 'Turkmenistani Manat', symbol: 'T', decimals: 2, label: 'TMT - Turkmenistani Manat (T)' },
  { code: 'TND', name: 'Tunisian Dinar', symbol: 'د.ت', decimals: 3, label: 'TND - Tunisian Dinar (د.ت)' },
  { code: 'TOP', name: 'Tongan Paʻanga', symbol: 'T$', decimals: 2, label: 'TOP - Tongan Paʻanga (T$)' },
  { code: 'TRY', name: 'Turkish Lira', symbol: '₺', decimals: 2, label: 'TRY - Turkish Lira (₺)' },
  { code: 'TTD', name: 'Trinidad & Tobago Dollar', symbol: '$', decimals: 2, label: 'TTD - Trinidad & Tobago Dollar ($)' },
  { code: 'TWD', name: 'New Taiwan Dollar', symbol: 'NT$', decimals: 2, label: 'TWD - New Taiwan Dollar (NT$)' },
  { code: 'TZS', name: 'Tanzanian Shilling', symbol: 'TSh', decimals: 2, label: 'TZS - Tanzanian Shilling (TSh)' },
  { code: 'UAH', name: 'Ukrainian Hryvnia', symbol: '₴', decimals: 2, label: 'UAH - Ukrainian Hryvnia (₴)' },
  { code: 'UGX', name: 'Ugandan Shilling', symbol: 'USh', decimals: 0, label: 'UGX - Ugandan Shilling (USh)' },
  { code: 'USD', name: 'United States Dollar', symbol: '$', decimals: 2, label: 'USD - United States Dollar ($)' },
  { code: 'UYU', name: 'Uruguayan Peso', symbol: '$', decimals: 2, label: 'UYU - Uruguayan Peso ($)' },
  { code: 'UZS', name: 'Uzbekistan Som', symbol: 'soʻm', decimals: 2, label: 'UZS - Uzbekistan Som (soʻm)' },
  { code: 'VES', name: 'Venezuelan Bolívar', symbol: 'Bs.S', decimals: 2, label: 'VES - Venezuelan Bolívar (Bs.S)' },
  { code: 'VND', name: 'Vietnamese Dong', symbol: '₫', decimals: 0, label: 'VND - Vietnamese Dong (₫)' },
  { code: 'VUV', name: 'Vanuatu Vatu', symbol: 'VT', decimals: 0, label: 'VUV - Vanuatu Vatu (VT)' },
  { code: 'WST', name: 'Samoan Tala', symbol: 'WS$', decimals: 2, label: 'WST - Samoan Tala (WS$)' },
  { code: 'XAF', name: 'Central African CFA Franc', symbol: 'Fr', decimals: 0, label: 'XAF - Central African CFA Franc (Fr)' },
  { code: 'XCD', name: 'East Caribbean Dollar', symbol: '$', decimals: 2, label: 'XCD - East Caribbean Dollar ($)' },
  { code: 'XOF', name: 'West African CFA Franc', symbol: 'Fr', decimals: 0, label: 'XOF - West African CFA Franc (Fr)' },
  { code: 'XPF', name: 'CFP Franc', symbol: 'Fr', decimals: 0, label: 'XPF - CFP Franc (Fr)' },
  { code: 'YER', name: 'Yemeni Rial', symbol: '﷼', decimals: 2, label: 'YER - Yemeni Rial (﷼)' },
  { code: 'ZAR', name: 'South African Rand', symbol: 'R', decimals: 2, label: 'ZAR - South African Rand (R)' },
  { code: 'ZMW', name: 'Zambian Kwacha', symbol: 'ZK', decimals: 2, label: 'ZMW - Zambian Kwacha (ZK)' },
  { code: 'ZWL', name: 'Zimbabwean Dollar', symbol: '$', decimals: 2, label: 'ZWL - Zimbabwean Dollar ($)' },
];

/**
 * Fast lookup map for O(1) currency retrieval by ISO code.
 */
const CURRENCY_MAP = new Map<string, CurrencyInfo>(
  ISO_CURRENCIES.map((c) => [c.code, c])
);

/**
 * Check if a code is a valid, active ISO 4217 currency.
 */
export function isValidCurrencyCode(code: string): boolean {
  if (!code || typeof code !== 'string') return false;
  return CURRENCY_MAP.has(code.trim().toUpperCase());
}

/**
 * Get currency details by ISO code, with safe fallback to USD.
 */
export function getCurrencyInfo(code?: string): CurrencyInfo {
  if (!code) return CURRENCY_MAP.get('USD')!;
  const normalized = code.trim().toUpperCase();
  return (
    CURRENCY_MAP.get(normalized) || {
      code: normalized,
      name: normalized,
      symbol: normalized,
      decimals: 2,
      label: `${normalized} (${normalized})`,
    }
  );
}

/**
 * Get currency symbol by ISO code.
 */
export function getCurrencySymbol(code?: string): string {
  return getCurrencyInfo(code).symbol;
}

/**
 * Detect whether the user's current environment/locale indicates India.
 * Checks timeZone (e.g. Asia/Kolkata) and navigator languages (e.g. en-IN, hi-IN).
 */
export function isIndiaLocale(): boolean {
  try {
    if (typeof Intl !== 'undefined' && Intl.DateTimeFormat) {
      const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || '';
      if (tz === 'Asia/Kolkata' || tz === 'Asia/Calcutta' || tz.toLowerCase().includes('kolkata')) {
        return true;
      }
    }

    if (typeof navigator !== 'undefined') {
      const langs: string[] = [];
      if (navigator.language) langs.push(navigator.language);
      if (Array.isArray(navigator.languages)) langs.push(...navigator.languages);
      for (const lang of langs) {
        if (!lang) continue;
        const normalized = lang.toUpperCase();
        if (
          normalized === 'HI' ||
          normalized.endsWith('-IN') ||
          normalized.includes('-IN-') ||
          normalized.includes('_IN')
        ) {
          return true;
        }
      }
    }
  } catch {
    // Fail silently in restricted sandbox
  }
  return false;
}

/**
 * Detect the appropriate default currency for the user's locale.
 * Defaults to INR for India-based operators, USD otherwise.
 */
export function detectUserDefaultCurrency(): string {
  return isIndiaLocale() ? 'INR' : 'USD';
}

export interface FormatCurrencyOptions {
  locale?: string;
  useGrouping?: boolean;
}

/**
 * Format a financial amount using the business's configured currency.
 *
 * Utilizes Intl.NumberFormat with correct ISO 4217 decimal precision
 * (e.g., 0 decimals for JPY, 3 for KWD, 2 for INR/USD/EUR) and locale-aware
 * digit grouping (e.g., lakhs/crores in India when using en-IN).
 */
export function formatCurrency(
  amount: number | string | null | undefined,
  currencyCode = 'USD',
  options?: FormatCurrencyOptions | string
): string {
  const num = typeof amount === 'number' ? amount : Number(amount ?? 0);
  if (isNaN(num)) return '0.00';

  const code = (currencyCode || 'USD').trim().toUpperCase();
  const info = getCurrencyInfo(code);

  const opts: FormatCurrencyOptions =
    typeof options === 'string' ? { locale: options } : options || {};

  // Determine appropriate locale for rendering
  let targetLocale = opts.locale;
  if (!targetLocale) {
    if (code === 'INR') {
      targetLocale = 'en-IN';
    } else if (typeof navigator !== 'undefined' && navigator.language) {
      targetLocale = navigator.language;
    } else {
      targetLocale = 'en-US';
    }
  }

  const useGrouping = opts.useGrouping !== undefined ? opts.useGrouping : true;

  try {
    return new Intl.NumberFormat(targetLocale, {
      style: 'currency',
      currency: code,
      minimumFractionDigits: info.decimals,
      maximumFractionDigits: info.decimals,
      useGrouping,
    }).format(num);
  } catch {
    // Safe fallback if Intl currency formatting throws on unsupported custom environment
    return `${info.symbol} ${num.toFixed(info.decimals)}`;
  }
}
