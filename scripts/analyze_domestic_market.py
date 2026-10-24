#!/usr/bin/env python3
"""Offline quote-quality audit. Distinct displayed storefronts are not independent sellers."""
import html,re,statistics
from html.parser import HTMLParser
from dataclasses import dataclass,field
@dataclass
class Node:
 tag:str
 attrs:dict=field(default_factory=dict)
 children:list=field(default_factory=list)
 def has(self,c):return c in self.attrs.get('class','').split()
 def walk(self):
  yield self
  for x in self.children:
   if isinstance(x,Node):yield from x.walk()
 def text(self,direct=False):
  s=' '.join(x if isinstance(x,str) else '' if direct else x.text() for x in self.children)
  return re.sub(r'\s+',' ',html.unescape(s)).strip()
class Tree(HTMLParser):
 VOID={'input','img','br','hr','meta','link','source','wbr','area','base','embed','param','track','col'}
 def __init__(self):super().__init__();self.root=Node('root');self.stack=[self.root]
 def handle_starttag(self,t,a):
  n=Node(t,dict(a));self.stack[-1].children.append(n)
  if t not in self.VOID:self.stack.append(n)
 def handle_endtag(self,t):
  for i in range(len(self.stack)-1,0,-1):
   if self.stack[i].tag==t:del self.stack[i:];break
 def handle_data(self,d):self.stack[-1].children.append(d)
def number(s):
 m=re.fullmatch(r'[\d,]+',s.strip());return int(s.replace(',','')) if m else None
def parse_offers(source):
 parser=Tree();parser.feed(source);groups=[n for n in parser.root.walk() if n.tag=='ul' and n.has('list__mall-price')]
 result=[]
 for group in groups:
  for n in group.children:
   if not isinstance(n,Node) or n.tag!='li' or not n.has('list-item'):continue
   nodes=list(n.walk());p=next((x for x in nodes if x.has('text__num')),None);delivery=next((x for x in nodes if x.has('box__delivery')),None);logo=next((x for x in nodes if x.has('box__logo')),None)
   if not p or not logo:continue
   image=next((x for x in logo.walk() if x.tag=='img' and x.attrs.get('alt')),None)
   seller=image.attrs['alt'].strip() if image else logo.text();seller=re.sub(r'\s*(네이버페이|Npay)\s*$', '',seller).strip()
   label=delivery.text(direct=True) if delivery else ''
   ship=0 if label=='무료배송' else int(label[:-1].replace(',','')) if re.fullmatch(r'[\d,]+원',label) else None
   val=number(p.text());cash=any(x.has('badge__cash') for x in nodes) or any(x.text()=='현금' for x in nodes if x.tag=='span')
   if val and seller:result.append({'seller':seller,'productPrice':val,'shipping':ship,'deliveredPrice':val+ship if ship is not None else None,'shippingLabel':label,'cashOnly':cash})
 return result

def audit_quote(source,quote):
 offers=parse_offers(source);valid=[];seen=set()
 for x in offers:
  if x['cashOnly'] or x['deliveredPrice'] is None or x['seller'] in seen:continue
  seen.add(x['seller']);valid.append(x)
 by_product=sorted(valid,key=lambda x:x['productPrice'])[:3];by_total=sorted(valid,key=lambda x:x['deliveredPrice'])[:3]
 median=lambda a,k:statistics.median([x[k] for x in a]) if len(a)==3 else None
 first=next((x for x in offers if not x['cashOnly']),None)
 reconciled=bool(first and first['productPrice']==quote['productPrice'] and first['deliveredPrice']==quote['deliveredPrice'])
 return {'offers':offers,'distinctDisplayedStoresWithShipping':len(valid),'top3ProductMedian':median(by_product,'productPrice'),'top3DeliveredMedian':median(by_total,'deliveredPrice'),'top3DeliveredLow':min((x['deliveredPrice'] for x in by_total),default=None),'top3DeliveredHigh':max((x['deliveredPrice'] for x in by_total),default=None),'top3Stores':[x['seller'] for x in by_total],'top3ProductStores':[x['seller'] for x in by_product],'firstOfferReconciled':reconciled,'merchantStockVerified':False,'salesVolumeAvailable':False,'scope':'First displayed ordinary offers only; storefront labels, not independent seller/legal entity count. Regional/conditional delivery not verified.'}
