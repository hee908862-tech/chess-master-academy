import json,collections,xml.etree.ElementTree as ET
from pathlib import Path
p=Path('/tmp/cma-pr29-final-646');m=json.loads((p/'manifest.json').read_text())
assert m['status']=='complete',m['status']
expected=[l.strip() for l in (p/'collection.log').read_text().splitlines() if '::' in l and l.split('::')[0].endswith('.py')]
actual=[];counts=collections.Counter();suites=[]
for f in sorted(p.glob('suite-*.xml')):
 root=ET.parse(f).getroot();cases=root.findall('.//testcase');summary=collections.Counter()
 for c in cases:
  actual.append(c.attrib['classname'].replace('.','/')+'.py::'+c.attrib['name'])
  kind='failed' if c.find('failure') is not None else 'error' if c.find('error') is not None else 'skipped' if c.find('skipped') is not None else 'passed'
  counts[kind]+=1;summary[kind]+=1
 suites.append({'file':f.name,**summary})
result={'head':m['head'],'expected':len(expected),'executed':len(actual),'counts':dict(counts),'suites':suites,'duplicates':[k for k,v in collections.Counter(actual).items() if v>1],'missing':sorted(set(expected)-set(actual)),'unexpected':sorted(set(actual)-set(expected))}
(p/'verification.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
assert len(expected)==len(actual) and not result['duplicates'] and not result['missing'] and not result['unexpected']
assert not counts['failed'] and not counts['error'] and not counts['skipped']
