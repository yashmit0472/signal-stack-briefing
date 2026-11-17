"""Research three real companies. Operator decisions and interviews happen in the UI."""
from store_db import init,items,save
from jobs import execute
from concurrent.futures import ThreadPoolExecutor
def configure(pair):
    name,url=pair
    p=next((p for p in items('root','company') if p['url']==url),None)
    c=p['id'] if p else save('root','company',{'name':name,'url':url,'automation':False})
    if not p or not p.get('research'):execute(c,'research')
    if not items(c,'source'):execute(c,'discover')
    print(name,len(items(c,'source')),[(r['job'],r['status'],r.get('detail','')) for r in items(c,'run')[:2]],flush=True)
if __name__=='__main__':
    init()
    with ThreadPoolExecutor(2) as pool:list(pool.map(configure,[('MeetUniversity','https://www.meetuniversity.com/'),('Ghost','https://ghost.org/'),('Fairphone','https://www.fairphone.com/')]))

