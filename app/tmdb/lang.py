# -*- coding: utf-8 -*-
langs = {'AA': ['aa'], 'AB': ['ab'], 'AE': ['ae', 'ar'], 'AF': ['af'],
         'AK': ['ak'], 'AM': ['am'], 'AN': ['an'], 'SA': ['ar', 'sa'],
         'AS': ['as'], 'AV': ['av'], 'AY': ['ay'], 'AZ': ['az'], 'BA': ['ba'],
         'BY': ['be'], 'BG': ['bg'], 'BI': ['bi'], 'BM': ['bm'], 'BD': ['bn'],
         'BO': ['bo'], 'BR': ['br', 'pt'], 'BS': ['bs'],
         'ES': ['ca', 'es', 'eu', 'gl'], 'CE': ['ce'], 'GU': ['ch', 'gu'],
         'CN': ['cn', 'zh'], 'CO': ['co'], 'CR': ['cr'], 'CZ': ['cs'],
         'CU': ['cu'], 'CV': ['cv'], 'CY': ['cy'], 'DK': ['da'], 'DE': ['de'],
         'AT': ['de'], 'CH': ['de'], 'DV': ['dv'], 'DZ': ['dz'],
         'EE': ['ee', 'et'], 'GR': ['el'], 'US': ['en'], 'AU': ['en'],
         'CA': ['en', 'fr'], 'GB': ['en'], 'IE': ['en', 'ie'], 'NZ': ['en'],
         'EO': ['eo'], 'MX': ['es'], 'IR': ['fa'], 'FF': ['ff'], 'FI': ['fi'],
         'FJ': ['fj'], 'FO': ['fo'], 'FR': ['fr'], 'FY': ['fy'], 'GA': ['ga'],
         'GD': ['gd'], 'GN': ['gn'], 'GV': ['gv'], 'HA': ['ha'], 'IL': ['he'],
         'IN': ['hi', 'kn', 'ml', 'ta', 'te'], 'HO': ['ho'], 'HR': ['hr'],
         'HT': ['ht'], 'HU': ['hu'], 'HY': ['hy'], 'HZ': ['hz'], 'IA': ['ia'],
         'ID': ['id'], 'IG': ['ig'], 'II': ['ii'], 'IK': ['ik'], 'IO': ['io'],
         'IS': ['is'], 'IT': ['it'], 'IU': ['iu'], 'JP': ['ja'], 'JV': ['jv'],
         'GE': ['ka'], 'KG': ['kg'], 'KI': ['ki'], 'KJ': ['kj'], 'KZ': ['kk'],
         'KL': ['kl'], 'KM': ['km'], 'KR': ['ko', 'kr'], 'KS': ['ks'],
         'KU': ['ku'], 'KV': ['kv'], 'KW': ['kw'], 'KY': ['ky'], 'LA': ['la'],
         'LB': ['lb'], 'LG': ['lg'], 'LI': ['li'], 'LN': ['ln'], 'LO': ['lo'],
         'LT': ['lt'], 'LU': ['lu'], 'LV': ['lv'], 'MG': ['mg'], 'MH': ['mh'],
         'MI': ['mi'], 'MK': ['mk'], 'MN': ['mn'], 'MO': ['mo'], 'MR': ['mr'],
         'MY': ['ms', 'my'], 'SG': ['ms', 'sg'], 'MT': ['mt'], 'NA': ['na'],
         'NO': ['nb', 'no'], 'ND': ['nd'], 'NE': ['ne'], 'NG': ['ng'],
         'NL': ['nl'], 'NN': ['nn'], 'NR': ['nr'], 'NV': ['nv'], 'NY': ['ny'],
         'OC': ['oc'], 'OJ': ['oj'], 'OM': ['om'], 'OR': ['or'], 'OS': ['os'],
         'PA': ['pa'], 'PI': ['pi'], 'PL': ['pl'], 'PS': ['ps'], 'PT': ['pt'],
         'QU': ['qu'], 'RM': ['rm'], 'RN': ['rn'], 'RO': ['ro'], 'RU': ['ru'],
         'RW': ['rw'], 'SC': ['sc'], 'SD': ['sd'], 'SE': ['se', 'sv'],
         'SH': ['sh'], 'LK': ['si'], 'SK': ['sk'], 'SI': ['sl'], 'SM': ['sm'],
         'SN': ['sn'], 'SO': ['so'], 'AL': ['sq'], 'RS': ['sr'], 'SS': ['ss'],
         'ST': ['st'], 'SU': ['su'], 'SW': ['sw'], 'TG': ['tg'], 'TH': ['th'],
         'TI': ['ti'], 'TK': ['tk'], 'PH': ['tl'], 'TN': ['tn'], 'TO': ['to'],
         'TR': ['tr'], 'TS': ['ts'], 'TT': ['tt'], 'TW': ['tw', 'zh'],
         'TY': ['ty'], 'UG': ['ug'], 'UA': ['uk'], 'UR': ['ur'], 'UZ': ['uz'],
         'VE': ['ve'], 'VN': ['vi'], 'VO': ['vo'], 'WA': ['wa'], 'WO': ['wo'],
         'XH': ['xh'], 'XX': ['xx'], 'YI': ['yi'], 'YO': ['yo'],
         'ZA': ['za', 'zu'], 'HK': ['zh']}


def get_langs(countries: list) -> list:
    res = set()
    for country in countries:
        if country in langs.keys():
            res.update(langs[country])

    return list(res)
