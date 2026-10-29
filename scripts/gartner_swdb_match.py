"""
Match Spiceworks (SWDB) products to Gartner Peer Insights products.

Pipeline
  1. Normalize names (ASCII, lowercase, '&'->and, drop legal suffixes for vendor keys).
  2. Resolve candidate Gartner vendors for each SWDB row via several routes:
       vendor_exact   normalized SW vendor == a Gartner vendor key (full, outer, or "(Sub)" part)
       cpe_vendor     SW cpe_vendor == Gartner vendor key
       product_brand  first 1-3 tokens of the SW product == Gartner vendor key (non-generic)
       alias          hand-curated M&A / rename table (Kronos->UKG, Siebel->Oracle, ...)
       vendor_fuzzy   rapidfuzz ratio >= 90 on compact vendor keys (weak)
       *_family       other Gartner vendors sharing the parent's first token (Cisco Systems / Cisco (Slido))
  3. Within candidate vendors, compare product "cores" (product minus leading vendor tokens,
     versions, "(Legacy)", parenthetical acronyms).
  4. Vendor-agnostic lookup: unique exact full-name match anywhere in Gartner.
  5. Assign tiers: A_* = auto-accept, B_* = needs review, X_* = no product match.

Usage: python gartner_swdb_match.py GARTNER.xlsx SWDB.csv OUT.xlsx
"""
import re, sys, unicodedata
from collections import defaultdict
import numpy as np, pandas as pd
from rapidfuzz import fuzz, process

LEGAL = (r'\b(inc|incorporated|llc|l l c|ltd|limited|corp|corporation|co|company|gmbh|ag|sa|srl|sas|spa|bv|b v|plc|pty|oy|ab|nv|kk|pvt|private|'
         r'group|holdings|holding|technologies|technology|tech|software|softwares|systems|system|solutions|international|intl|labs|networks|'
         r'communications|the|com|io|americas|usa|us|operating)\b')
VER = r'\b(v?\d+(\.\d+)+|(19|20)\d\d|\d+(\.\d+)?x)\b'
GENERIC = set(('cloud platform suite software enterprise management manager services service solution solutions online edition '
               'pro system systems business center centre portal app apps and for of the on series hub plus advanced standard '
               'professional express core global international saas tool tools new').split())
SAFE_EXTRA = set('platform suite edition enterprise software system systems solution solutions one'.split())  # qualifiers that don't change the product
BRAND_SUFFIX = GENERIC | set('one ai iq 360 crm erp hcm lms ats psa cdn x go cloud platform'.split())
from wordfreq import zipf_frequency
def is_common(name):
    """True if every token is an ordinary English word (e.g. 'sense', 'conductor') -> name alone is not identifying."""
    t = name.split()
    return bool(t) and all(zipf_frequency(w, 'en') >= 2.5 for w in t)

def norm(x):
    if not isinstance(x, str): return ''
    x = unicodedata.normalize('NFKD', x).encode('ascii', 'ignore').decode().lower().replace('&', ' and ')
    x = re.sub(r"[’']", '', x); x = re.sub(r'[^a-z0-9+#]', ' ', x)
    return re.sub(r'\s+', ' ', x).strip()

def vkey(x):
    k = re.sub(r'\s+', ' ', re.sub(LEGAL, ' ', norm(x))).strip()
    return k or norm(x)

def compact(x): return vkey(x).replace(' ', '')
def outer(v): return re.sub(r'\s*\([^)]*\)', '', v)
def stem(w): return w[:-1] if len(w) > 4 and w.endswith('s') else w
def toks(x): return {stem(w) for w in x.split()}
def nomodel(x): return ' '.join(w for w in x.split() if not re.search(r'\d', w))
def clean_prod(p, drop_paren=False):
    p = re.sub(r'\((legacy|retired)\)', '', str(p), flags=re.I)
    if drop_paren: p = re.sub(r'\([^)]*\)', '', p)
    return re.sub(r'\s+', ' ', re.sub(VER, ' ', norm(p))).strip()

def strip_lead(n, keys):
    t = n.split(); changed = True
    keys = sorted({k for k in keys if k}, key=lambda z: -len(z.split()))
    while changed and t:
        changed = False
        for k in keys:
            kt = k.split()
            if t[:len(kt)] == kt: t = t[len(kt):]; changed = True; break
        if not changed and t[0] == 'the': t = t[1:]; changed = True
    return ' '.join(t)

ALIAS_RAW = {  # SW vendor/brand -> Gartner vendor(s). Extend as needed.
 'ca':['Broadcom'],'ca technologies':['Broadcom'],'symantec':['Broadcom'],'altiris':['Broadcom'],'vmware':['Broadcom (VMware)'],
 'pivotalsoft':['Broadcom (VMware)'],'pivotal':['Broadcom (VMware)'],'airwatch':['Broadcom (VMware)'],
 'micro-focus':['OpenText'],'micro focus':['OpenText'],'novell':['OpenText'],'kronos':['UKG'],'ultimate':['UKG'],
 'mailchimp':['Intuit'],'rocket science group':['Intuit'],'quickbooks':['Intuit'],'mcafee':['Trellix','Skyhigh Security'],'fireeye':['Trellix'],
 'dell emc':['Dell Technologies'],'emc':['Dell Technologies'],'centurylink':['Lumen'],'level 3':['Lumen'],'qwest':['Lumen'],
 'hashicorp':['IBM'],'cognos':['IBM'],'kenexa':['IBM'],'q1labs':['IBM'],'apptio':['IBM'],'turbonomic':['IBM'],'red-hat':['IBM (Red Hat)'],'red hat':['IBM (Red Hat)'],
 'juniper':['Hewlett Packard Enterprise (HPE)'],'aruba':['Hewlett Packard Enterprise (HPE)'],'skype':['Microsoft'],'linkedin':['Microsoft'],
 'github':['Microsoft'],'yammer':['Microsoft'],'nuancecomms':['Microsoft'],'nuance':['Microsoft'],'appnexus':['Microsoft'],
 'siebel':['Oracle'],'hyperion':['Oracle'],'jd-edwards':['Oracle'],'bea-systems':['Oracle'],'netsuite':['Oracle'],'iplanet':['Oracle'],
 'sun microsystems':['Oracle'],'eloqua':['Oracle'],'responsys':['Oracle'],'taleo':['Oracle'],'micros':['Oracle'],
 'exacttarget':['Salesforce'],'mulesoft':['Salesforce'],'demandware':['Salesforce'],'heroku':['Salesforce'],'tableau':['Salesforce (Tableau)'],
 'slack':['Salesforce (Slack)'],'informatica':['Salesforce (Informatica)'],'marketo':['Adobe'],'magento':['Adobe'],'omniture':['Adobe'],'workfront':['Adobe'],
 'concur':['SAP'],'sap ariba':['SAP'],'ariba':['SAP'],'successfactors':['SAP'],'sybase':['SAP'],'hybris':['SAP'],
 'talend':['Qlik'],'attunity':['Qlik'],'qliktech':['Qlik'],'sendgrid':['Twilio'],'segment':['Twilio'],'veritas':['Cohesity'],
 'apache-soft':['Apache Software Foundation'],'apache':['Apache Software Foundation'],'ubuntu':['Canonical'],'facebook':['Meta'],
 'incapsula':['Thales Group (Imperva)'],'imperva':['Thales Group (Imperva)'],'jda-sftwr':['Blue Yonder'],'jda':['Blue Yonder'],
 'polycom':['HP'],'plantronics':['HP'],'rockwelauto':['Rockwell Automation'],'thmsnreutrs':['Thomson Reuters'],'wolterkluwr':['Wolters Kluwer'],
 'meraki':['Cisco Systems'],'opendns':['Cisco Systems'],'duo security':['Cisco Systems'],'appdynamics':['Cisco Systems'],'splunk':['Cisco Systems (Splunk)'],
 'elstcsearch':['Elastic'],'nginx':['F5'],'f5-networks':['F5'],'starfield':['GoDaddy'],'pingidentit':['Ping Identity'],
 'amazon':['Amazon Web Services (AWS)'],'amazon web services':['Amazon Web Services (AWS)'],
}

def main(gpath, spath, outpath):
    G_all = pd.read_excel(gpath, 'Products')
    gu = G_all.drop_duplicates('Product URL').reset_index(drop=True)
    s = pd.read_csv(spath, low_memory=False)
    gvendors = set(gu.Vendor)
    ALIAS = {compact(k): v for k, v in ALIAS_RAW.items()}
    for vs in ALIAS.values():
        for v in vs: assert v in gvendors, f'alias target not in Gartner: {v}'

    # ---------- Gartner vendor keys
    gvkeys = defaultdict(set); key2v = defaultdict(set)
    for v in gvendors:
        ks = {vkey(v), vkey(outer(v)), norm(v), norm(outer(v))} | {vkey(i) for i in re.findall(r'\(([^)]+)\)', v)}
        ks = {k for k in ks if len(k) >= 2}
        gvkeys[v] |= ks
        for k in ks: key2v[k.replace(' ', '')].add(v)
    fam = defaultdict(set)
    for v in gvendors:
        o = norm(outer(v)).split()
        if o and len(o[0]) >= 4: fam[o[0]].add(v)

    # ---------- Gartner product strings
    gu['full'] = gu.Product.map(clean_prod)
    gu['full_np'] = gu.Product.map(lambda p: clean_prod(p, True))
    gu['core'] = [strip_lead(clean_prod(p), gvkeys[v]) for p, v in zip(gu.Product, gu.Vendor)]
    gu['core_np'] = [strip_lead(clean_prod(p, True), gvkeys[v]) for p, v in zip(gu.Product, gu.Vendor)]
    byv = {v: np.array(ix) for v, ix in gu.groupby('Vendor').indices.items()}
    full_idx = defaultdict(set); core_gidx = defaultdict(set)
    for i, (a, b, c, d) in enumerate(zip(gu.full, gu.full_np, gu.core, gu.core_np)):
        for k in (a, b):
            if k: full_idx[k].add(i)
        for k in (c, d):
            if k: core_gidx[k].add(i)
    gu['nrat'] = G_all.groupby('Product URL')['# Ratings'].max().reindex(gu['Product URL']).fillna(0).values

    # ---------- SW vendor candidates
    s['vk'] = s.VendorName.map(vkey); s['vc'] = s.VendorName.map(compact)
    s['full'] = s.Product.map(clean_prod)
    allkeys = list(key2v.keys())
    fuzzy_cache = {}
    def candidates(r):
        c = {}
        def add(vs, how):
            for v in vs: c.setdefault(v, how)
        add(key2v.get(r.vc, ()), 'vendor_exact')
        if isinstance(r.cpe_vendor, str): add(key2v.get(compact(r.cpe_vendor.replace('_', ' ')), ()), 'cpe_vendor')
        pt = norm(r.Product).split()
        for n in (3, 2, 1):
            if len(pt) >= n:
                brand = ' '.join(pt[:n])
                if set(brand.split()) <= GENERIC: continue
                k = compact(brand)
                if len(k) >= 4: add(key2v.get(k, ()), 'product_brand')
        for k in {r.vc, compact(' '.join(pt[:2])), compact(pt[0]) if pt else ''}:
            add(ALIAS.get(k, ()), 'alias')
        if not c and len(r.vc) >= 5:
            if r.vc not in fuzzy_cache:
                fuzzy_cache[r.vc] = process.extractOne(r.vc, allkeys, scorer=fuzz.ratio, score_cutoff=90)
            m = fuzzy_cache[r.vc]
            if m: add(key2v[m[0]], 'vendor_fuzzy')
        for v, how in list(c.items()):
            o = norm(outer(v)).split()
            if o and len(o[0]) >= 4 and len(fam[o[0]]) <= 8:
                for v2 in fam[o[0]]: c.setdefault(v2, how + '_family')
        return c
    s['cand'] = s.apply(candidates, axis=1)

    STRONG = {'vendor_exact', 'cpe_vendor', 'product_brand', 'alias'}
    def typo_ok(a, b):
        """every non-generic token that differs must have a near-identical partner (typo / abbreviation)."""
        A, B = toks(a) - toks(b) - GENERIC, toks(b) - toks(a) - GENERIC
        A = {x for x in A if not any(fuzz.ratio(x, y) >= 80 for y in B)}
        B = {y for y in B if not any(fuzz.ratio(x, y) >= 80 for x in toks(a))}
        return not (A and B)   # conflict only when both sides carry an unmatched distinctive token (substitution)

    out = []
    for r in s.itertuples():
        swkeys = {r.vk, norm(r.VendorName)} | {k for v in r.cand for k in gvkeys[v]}
        c_sw = strip_lead(r.full, swkeys)
        sw_brand = norm(r.Product)
        best = None
        for v, how in r.cand.items():
            base = how.replace('_family', ''); fam_ = how.endswith('_family')
            strong = base in STRONG
            ids = byv[v]
            for i in ids:
                gf, gfn, gc, gcn = gu.full.iat[i], gu.full_np.iat[i], gu.core.iat[i], gu.core_np.iat[i]
                if r.full and r.full in (gf, gfn):                 sc, kind = 100, 'full_exact'
                elif c_sw and c_sw in (gc, gcn):                    sc, kind = 100, 'core_exact'
                elif not c_sw:      # SW product is only the brand
                    if fuzz.ratio(sw_brand, gfn) >= 88 or (len(r.vk) >= 5 and not is_common(r.vk) and fuzz.ratio(r.vk, gfn) >= 88): sc, kind = 99, 'brand_eq_product'
                    elif (gcn and not fam_ and set(gcn.split()) <= BRAND_SUFFIX and gfn.endswith(gcn)
                          and compact(sw_brand) == gfn[:len(gfn) - len(gcn)].replace(' ', '')):   # exact brand + suffix
                        sc, kind = 95, 'brand_plus_suffix'
                    elif len(ids) == 1 and not fam_ and base in ('vendor_exact', 'cpe_vendor', 'alias'): sc, kind = 80, 'single_product_vendor'
                    elif (not fam_ and base in ('vendor_exact', 'cpe_vendor', 'alias', 'product_brand')
                          and (compact(sw_brand) in {k.replace(' ', '') for k in gvkeys[v]} or fuzz.ratio(compact(sw_brand), compact(outer(v))) >= 85)):
                        sc, kind = 70 + min(7.9, np.log1p(gu.nrat.iat[i])), 'brand_to_flagship'
                    else: continue
                elif not gcn:
                    sc, kind = fuzz.ratio(r.full, gfn) * 0.9, 'fuzzy_full'
                else:
                    sc = max(fuzz.ratio(c_sw, gcn), fuzz.token_sort_ratio(c_sw, gcn)); kind = 'fuzzy_core'
                    if sc >= 90 and not typo_ok(c_sw, gcn): sc, kind = 75, 'fuzzy_core_conflict'
                    if sc < 90:
                        a, b = toks(c_sw), toks(gcn)
                        am, bm = toks(nomodel(c_sw)), toks(nomodel(gcn))
                        has_d = lambda z: any(re.search(r'\d', w) for w in z.split())
                        if am and am == bm and (am - GENERIC) and has_d(c_sw) and not has_d(gcn):                          sc, kind = 91, 'model_family'
                        elif b and b < a and (b - GENERIC):
                            extra = a - b
                            sc, kind = (90, 'g_in_sw_generic') if extra <= GENERIC | {w for w in extra if re.search(r'\d', w)} else (86, 'g_in_sw_parent')
                        elif a and a < b and (a - GENERIC):
                            extra = b - a
                            sc, kind = (90, 'sw_in_g_generic') if extra <= SAFE_EXTRA else (84, 'sw_in_g_specific')
                key = (sc, strong and not (fam_ and kind not in ('full_exact', 'core_exact')), -len(ids))
                if best is None or key > best[0]:
                    best = (key, sc, kind, int(i), v, how)
        glob = None
        resolved = {v for v, h in r.cand.items() if h in STRONG}   # vendors confidently resolved for this row
        for k, idx_ in ((r.full, full_idx), (r.full, core_gidx)):
            if glob: break
            if k and len(k) >= 3 and not set(k.split()) <= GENERIC and len(idx_.get(k, ())) == 1 and not (len(k) < 5 and is_common(k)):
                gi_ = next(iter(idx_[k])); gv_ = gu.Vendor.iat[gi_]
                vsim = max(fuzz.token_set_ratio(r.vk, vkey(gv_)), max((fuzz.token_set_ratio(r.vk, x) for x in gvkeys[gv_]), default=0))
                conflict = bool(resolved) and gv_ not in resolved and vsim < 80   # e.g. Cisco 'WLAN' -> Huawei WLAN
                ok = ((not is_common(k)) or vsim >= 80) and not conflict
                glob = (None, 100, 'global_full_exact' if ok else 'global_full_exact_commonword', gi_, gv_, 'none')
        out.append((c_sw, best, glob))

    s['sw_core'] = [o[0] for o in out]
    def tier(o):
        _, b, gl = o
        if b:
            (_, strong, _), sc, kind, i, v, how = b
            if strong:
                if kind in ('full_exact', 'core_exact', 'brand_eq_product', 'brand_plus_suffix'): return 'A1_exact', b
                if kind == 'fuzzy_core' and sc >= 92:                            return 'A2_fuzzy_high', b
                if kind in ('model_family', 'g_in_sw_generic', 'sw_in_g_generic'): return 'A3_family_generic', b
        if gl and gl[2] == 'global_full_exact':                                  return 'A4_global_exact', gl
        if b:
            (_, strong, _), sc, kind, i, v, how = b
            if how.startswith('vendor_fuzzy'):                                  return 'X2_no_vendor', None   # validated 0/15 correct
            if kind == 'single_product_vendor':                                 return 'B2_single_product_vendor', b
            if kind == 'brand_to_flagship' and not gl:                         return 'B6_brand_to_flagship', b
            if kind in ('g_in_sw_parent', 'sw_in_g_specific', 'model_family', 'g_in_sw_generic', 'sw_in_g_generic'): return 'B3_containment', b
            if sc >= 82:                                                        return 'B4_fuzzy_mid', b
        if gl:                                                                   return 'B5_global_commonword', gl
        if b and b[0][1]:                                                       return 'X1_vendor_only', b
        return 'X2_no_vendor', None
    T = [tier(o) for o in out]
    s['tier'] = [t[0] for t in T]
    m = [t[1] for t in T]
    s['match_kind'] = [x[2] if x else None for x in m]
    s['score'] = [round(x[1], 1) if x else None for x in m]
    s['vendor_route'] = [x[5] if x else None for x in m]
    gi = [x[3] if x else None for x in m]
    for col, src in (('G_Vendor', 'Vendor'), ('G_Product', 'Product'), ('G_URL', 'Product URL')):
        s[col] = [gu[src].iat[i] if i is not None else None for i in gi]
    s.loc[s.tier.str.startswith('X'), ['G_Vendor', 'G_Product', 'G_URL']] = None
    s.loc[s.tier == 'X1_vendor_only', 'G_Vendor'] = [x[4] for x, t in zip(m, s.tier) if t == 'X1_vendor_only']
    # attach Gartner subcategories of the matched product
    cats = G_all.groupby('Product URL').agg(G_MainCategory=('Main Category', lambda x: ' | '.join(dict.fromkeys(x))),
                                            G_Subcategory=('Subcategory', lambda x: ' | '.join(dict.fromkeys(x))))
    s = s.merge(cats, how='left', left_on='G_URL', right_index=True)
    return s, gu

if __name__ == '__main__':
    s, gu = main(*sys.argv[1:3], None)
    s.to_pickle(sys.argv[3] if len(sys.argv) > 3 else 's_final.pkl')
    print(s.tier.value_counts().sort_index())
    print('\nShare of US Sites by tier'); print((s.groupby('tier')['US Sites'].sum() / s['US Sites'].sum()).round(3))
