"""Controller-only JavaScript checks, not browser or motion verification."""
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def function_source(path, name):
    source=(ROOT/path).read_text()
    start=source.index('async function '+name+'(')
    opening=source.index('{',start)
    depth=0
    for end in range(opening,len(source)):
        if source[end]=='{':depth+=1
        elif source[end]=='}':depth-=1
        if depth==0:return source[start:end+1]
    raise AssertionError('unterminated controller')



def test_repeated_selection_cancels_and_friendly_selection_switches():
    for filename in ['journey.js','repertoire.js','education.js']:
        function=function_source('public/'+filename,'click')
        script='''let selected='b7',busy=false,needsRefresh=false,failed=false;
let session={phase:'question',question:{legal:['b7b6','a7a6']}};
let data={active:{legal:['b7b6','a7a6'],step:{kind:'move'}}};
let draws=0;function renderBoard(){draws++}function draw(){draws++}
'''+function+'''
(async()=>{await click('b7');if(selected!==null||draws!==1)throw Error('same-square cancellation');await click('a7');if(selected!=='a7')throw Error('selection');await click('b7');if(selected!=='b7')throw Error('switch');})();'''
        result=subprocess.run(['node','-e',script],capture_output=True,text=True)
        assert result.returncode==0,(filename,result.stderr)
