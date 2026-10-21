"""Compile a tiny, finite local-only demo from existing authored foundations.
Every initial legal move and resulting FEN is enumerated by python-chess.
This is not a general chess engine, assessment, or persisted learning attempt.
"""
import json
from pathlib import Path
import chess
from foundation_content import BY_ID

def payload():
 rows=[]
 for course,index,puzzle in [('rook-bishop',1,False),('knight-queen',0,False),('mate-stalemate',0,True)]:
  s=BY_ID[course]['steps'][index];b=chess.Board(s['fen']);moves={}
  for m in b.legal_moves:
   after=b.copy();after.push(m)
   moves[m.uci()]={'fen':after.fen(),'accepted':after.is_checkmate() if puzzle else m.uci()==s['line'][0],'checkmate':after.is_checkmate()}
  rows.append({'id':course+'-'+str(index),'source':{'course':course,'step':index},'title':'한 수 체크메이트 예제' if puzzle else s['title'],'goal':'백 차례입니다. 한 수로 체크메이트를 만들어 보세요. 정답은 도움을 눌렀을 때만 표시합니다.' if puzzle else s['text'],'reason':s['reason'],'fen':s['fen'],'answer':s['line'][0],'puzzle':puzzle,'moves':moves})
 return {'version':1,'scope':'기존 자체 작성 기초에서 고른 2개 실습과 1개 예제 퍼즐. 이 화면 안에서만 유지되며 정식 기록/점수로 이전하지 않습니다.','examples':rows}
if __name__=='__main__':Path('public/guest-examples.json').write_text(json.dumps(payload(),ensure_ascii=False,indent=2)+'\n')
