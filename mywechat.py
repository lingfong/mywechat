#!/usr/bin/env python
# coding=utf-8
import ssl
import requests
import time
import re
import os
import sys
import xml.dom.minidom
import json
import threading
from datetime import datetime, timedelta
from threading import Timer
import time
import urllib
import random
import aiml
import os
os.chdir('./alice')
alice = aiml.Kernel()

MAX_GROUP_NUM = 2  # 每组人数
QRImagePath = os.path.join(os.getcwd(), 'qrcode.jpg')
deviceId = 'e000000000000000'
DEBUG=False
MemberList=[]           #好友详细信息
FriendUserNameList=[]       #好友username
INTERFACE_CALLING_INTERVAL=5
tasks=[]
QunList=[]                #最近联系的群username
qunMemberList=[]              #最近联系的人的群成员
noRobotList=[]
#init获取的联系人不全
#第二次sync心跳包的时候可以获取所有最近联系人

#登录模块源自https://github.com/0x5e/wechat-deleted-friends
def getUUID():
    global uuid

    url = 'https://login.weixin.qq.com/jslogin'
    params = {
        'appid': 'wx782c26e4c19acffb',
        'fun': 'new',
        'lang': 'zh_CN',
        '_': int(time.time()),
    }

    r= myRequests.get(url=url, params=params)
    r.encoding = 'utf-8'
    data = r.text

    # print(data)

    # window.QRLogin.code = 200; window.QRLogin.uuid = "oZwt_bFfRg==";
    regx = r'window.QRLogin.code = (\d+); window.QRLogin.uuid = "(\S+?)"'
    pm = re.search(regx, data)

    code = pm.group(1)
    uuid = pm.group(2)

    if code == '200':
        return True

    return False

def showQRImage():
    global tip

    url = 'https://login.weixin.qq.com/qrcode/' + uuid
    params = {
        't': 'webwx',
        '_': int(time.time()),
    }

    r = myRequests.get(url=url, params=params)

    tip = 1

    f = open(QRImagePath, 'wb')
    f.write(r.content)
    f.close()
    os.startfile(QRImagePath)
    print('请使用微信扫描二维码以登录')

def waitForLogin():
    global tip, base_uri, redirect_uri, push_uri

    url = 'https://login.weixin.qq.com/cgi-bin/mmwebwx-bin/login?tip=%s&uuid=%s&_=%s' % (
        tip, uuid, int(time.time()))

    r = myRequests.get(url=url)
    r.encoding = 'utf-8'
    data = r.text

    # print(data)

    # window.code=500;
    regx = r'window.code=(\d+);'
    pm = re.search(regx, data)

    code = pm.group(1)

    if code == '201':  # 已扫描
        print('成功扫描,请在手机上点击确认以登录')
        tip = 0
    elif code == '200':  # 已登录
        print('正在登录...')
        regx = r'window.redirect_uri="(\S+?)";'
        pm = re.search(regx, data)
        redirect_uri = pm.group(1) + '&fun=new'
        base_uri = redirect_uri[:redirect_uri.rfind('/')]

        # push_uri与base_uri对应关系(排名分先后)(就是这么奇葩..)
        services = [
            ('wx2.qq.com', 'webpush2.weixin.qq.com'),
            ('qq.com', 'webpush.weixin.qq.com'),
            ('web1.wechat.com', 'webpush1.wechat.com'),
            ('web2.wechat.com', 'webpush2.wechat.com'),
            ('wechat.com', 'webpush.wechat.com'),
            ('web1.wechatapp.com', 'webpush1.wechatapp.com'),
        ]
        push_uri = base_uri
        for (searchUrl, pushUrl) in services:
            if base_uri.find(searchUrl) >= 0:
                push_uri = 'https://%s/cgi-bin/mmwebwx-bin' % pushUrl
                break

        # closeQRImage
        if sys.platform.find('darwin') >= 0:  # for OSX with Preview
            os.system("osascript -e 'quit app \"Preview\"'")
    elif code == '408':  # 超时
        pass
    # elif code == '400' or code == '500':

    return code

def login():
    global skey, wxsid, wxuin, pass_ticket, BaseRequest

    r = myRequests.get(url=redirect_uri)
    r.encoding = 'utf-8'
    data = r.text

    # print(data)

    doc = xml.dom.minidom.parseString(data)
    root = doc.documentElement

    for node in root.childNodes:
        if node.nodeName == 'skey':
            skey = node.childNodes[0].data
        elif node.nodeName == 'wxsid':
            wxsid = node.childNodes[0].data
        elif node.nodeName == 'wxuin':
            wxuin = node.childNodes[0].data
        elif node.nodeName == 'pass_ticket':
            pass_ticket = node.childNodes[0].data

    # print('skey: %s, wxsid: %s, wxuin: %s, pass_ticket: %s' % (skey, wxsid,
    # wxuin, pass_ticket))

    if not all((skey, wxsid, wxuin, pass_ticket)):
        return False

    BaseRequest = {
        'Uin': int(wxuin),
        'Sid': wxsid,
        'Skey': skey,
        'DeviceID': deviceId,
    }

    return True

def responseState(func, BaseResponse):
    ErrMsg = BaseResponse['ErrMsg']
    Ret = BaseResponse['Ret']
    if DEBUG or Ret != 0:
        print('func: %s, Ret: %d, ErrMsg: %s' % (func, Ret, ErrMsg))

    if Ret != 0:
        return False

    return True

def webwxinit():

    url = (base_uri +
        '/webwxinit?pass_ticket=%s&skey=%s&r=%s' % (
            pass_ticket, skey, int(time.time())) )
    params  = {'BaseRequest': BaseRequest }
    headers = {'content-type': 'application/json; charset=UTF-8'}

    r = myRequests.post(url=url, data=json.dumps(params),headers=headers)
    r.encoding = 'utf-8'
    data = r.json()

    if DEBUG:
        f = open(os.path.join(os.getcwd(), 'webwxinit.json'), 'wb')
        f.write(r.content)
        f.close()


    # print(data)

    global ContactList, My, SyncKey
    dic = data
    ContactList = dic['ContactList']
    My = dic['User']
    noRobotList.append(My['UserName'])
    SyncKey = dic['SyncKey']

    state = responseState('webwxinit', dic['BaseResponse'])
    return state


def webwxgetcontact():

    url = (base_uri +
        '/webwxgetcontact?pass_ticket=%s&skey=%s&r=%s' % (
            pass_ticket, skey, int(time.time())) )
    headers = {'content-type': 'application/json; charset=UTF-8'}


    r = myRequests.post(url=url,headers=headers)
    r.encoding = 'utf-8'
    data = r.json()

    if DEBUG:
        f = open(os.path.join(os.getcwd(), 'webwxgetcontact.json'), 'wb')
        f.write(r.content)
        f.close()

    # print(data)

    dic = data
    MemberList = dic['MemberList']

    # 倒序遍历,不然删除的时候出问题..
    SpecialUsers = ["newsapp", "fmessage", "filehelper", "weibo", "qqmail", "tmessage", "qmessage", "qqsync", "floatbottle", "lbsapp", "shakeapp", "medianote", "qqfriend", "readerapp", "blogapp", "facebookapp", "masssendapp",
                    "meishiapp", "feedsapp", "voip", "blogappweixin", "weixin", "brandsessionholder", "weixinreminder", "wxid_novlwrv3lqwv11", "gh_22b87fa7cb3c", "officialaccounts", "notification_messages", "wxitil", "userexperience_alarm"]
    for i in range(len(MemberList) - 1, -1, -1):
        Member = MemberList[i]
        if Member['VerifyFlag'] & 8 != 0:  # 公众号/服务号
            MemberList.remove(Member)
        elif Member['UserName'] in SpecialUsers:  # 特殊账号
            MemberList.remove(Member)
        elif Member['UserName'].find('@@') != -1:  # 群聊
            MemberList.remove(Member)
        elif Member['UserName'] == My['UserName']:  # 自己
            MemberList.remove(Member)
        else:
            FriendUserNameList.append(Member['UserName'])   #所有好友的username入数组

    return MemberList

def syncKey():
    SyncKeyItems = ['%s_%s' % (item['Key'], item['Val'])
                    for item in SyncKey['List']]
    SyncKeyStr = '|'.join(SyncKeyItems)
    return SyncKeyStr

def syncCheck():
    url = push_uri + '/synccheck?'
    params = {
        'skey': BaseRequest['Skey'],
        'sid': BaseRequest['Sid'],
        'uin': BaseRequest['Uin'],
        'deviceId': BaseRequest['DeviceID'],
        'synckey': syncKey(),
        'r': int(time.time()),
    }

    r = myRequests.get(url=url,params=params)
    r.encoding = 'utf-8'
    data = r.text

    # print(data)

    # window.synccheck={retcode:"0",selector:"2"}
    regx = r'window.synccheck={retcode:"(\d+)",selector:"(\d+)"}'
    pm = re.search(regx, data)

    retcode = pm.group(1)
    selector = pm.group(2)

    return selector

def notify():
    url = base_uri + '/webwxstatusnotify?lang=zh_CN&pass_ticket=%s' % (
         urllib.quote_plus(pass_ticket))
    ClientMsgId = '%s%s' % (int(time.time()), '300')
    params = {
        'BaseRequest': BaseRequest,
        'Code': '3',
        'FromUserName': My['UserName'],
        'ToUserName': My['UserName'],
        'ClientMsgId': ClientMsgId,
    }
    headers = {'content-type': 'application/json; charset=UTF-8'}

    r = myRequests.post(url=url, data=json.dumps(params))
    r.encoding = 'utf-8'
    data = r.json()
    dic = data
    state = responseState('notify', dic['BaseResponse'])
    return state

def getqunmember(qunList):
    qunList2=[]
    for qun in qunList:
        qunList2.append({"UserName":qun,"EncryChatRoomId":""})
    r = '%s%s' % (int(time.time()), '300')
    url = base_uri + '/webwxbatchgetcontact?type=ex&r=%s&lang=zh_CN&pass_ticket=%s' % (
        r, urllib.quote_plus(pass_ticket))
    params = {
        'BaseRequest': BaseRequest,
        'Count': str(len(QunList)),
        'List': qunList2,
    }
    headers = {'content-type': 'application/json; charset=UTF-8'}

    r = myRequests.post(url=url, data=json.dumps(params))
    r.encoding = 'utf-8'
    data = r.json()
    dic=data

    ContactList=dic['ContactList']
    for contact in ContactList:
        if contact['MemberCount']>1:
            for member in contact['MemberList']:
                if not member['UserName'] in qunMemberList:
                    qunMemberList.append(member['UserName'])


    state = responseState('getqunmember', dic['BaseResponse'])
    return state

def webwxsync():
    global SyncKey

    url = base_uri + '/webwxsync?lang=zh_CN&skey=%s&sid=%s&pass_ticket=%s' % (
        BaseRequest['Skey'], BaseRequest['Sid'], urllib.quote_plus(pass_ticket))
    params = {
        'BaseRequest': BaseRequest,
        'SyncKey': SyncKey,
        'rr': ~int(time.time()),
    }
    headers = {'content-type': 'application/json; charset=UTF-8'}

    r = myRequests.post(url=url, data=json.dumps(params))
    r.encoding = 'utf-8'
    data = r.json()

    # print(data)

    dic = data
    try:
        if not int(dic['AddMsgCount'])==0:   #有新消息
                for message in dic['AddMsgList']:
                    if message['MsgType']==1: #新消息，文字消息
                        try:
                            print message['FromUserName'],message['Content']
                        except:
                            print message['FromUserName'],'can not  print'
                        if  message['FromUserName'] in noRobotList:
                            continue
                        if '@@' in message['FromUserName']:   #不回复群
                            continue
                        url = 'https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxsendmsg'
                        ids=random.randint(1000000,8999999)
                        ClientMsgID = '%s%s' % (int(time.time()),ids)
                        myWords=alice.respond(message['Content'])
                        print 'reply:'+myWords
                        Msg = {
                            'Type': 1,
                            'Content':myWords+ '------reply from a robot named alice',
                            'FromUserName': My["UserName"],
                            'ToUserName': message['FromUserName'],
                            'LocalID': ClientMsgID,
                            'ClientMsgId': ClientMsgID
                        }

                        params = {
                            'BaseRequest': BaseRequest,
                            'Msg': Msg,
                            'Scene': '0'
                        }
                        headers = {'content-type': 'application/json; charset=UTF-8'}

                        r = myRequests.post(url=url, data=json.dumps(params), headers=headers)
                        r.encoding = 'utf-8'
                        data = r.json()
                        pass
                    if message['MsgType'] == 51:  # 最近联系人消息，可以获取群号
                        if not len(QunList) == 0:
                            continue
                        if message['StatusNotifyUserName'] !='':
                            lists=message['StatusNotifyUserName'].split(',')
                            if len(lists)>0:
                                for UserName in lists:
                                    if UserName.find('@@') != -1:  # 群聊
                                        QunList.append(UserName)
    except:
        print 'error'
        pass

    SyncKey = dic['SyncKey']

    state = responseState('webwxsync', dic['BaseResponse'])
    return state


def heartBeatLoop():
    while True:
        syncCheck()
        webwxsync()
        """
        selector = syncCheck()
        print 'heart beat '+selector
        if selector != '0':
            print 'msg'
            webwxsync()
        """
        time.sleep(1)



def sendMsg(receiver,wordsToSend):  #
    ToUserName=""
    for member in FriendMemberList:
        if not receiver == "":
            if member['NickName'] == receiver:
                ToUserName = member['UserName']
                break
            if member['PYQuanPin'] == receiver:
                ToUserName = member['UserName']
                break
            if member['RemarkPYQuanPin'] == receiver:
                ToUserName = member['UserName']
                break
    if ToUserName=="":
        print("没找到该好友")
    url = 'https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxsendmsg'
    LocalID='%s%s'%(int(time.time()),'1234567')
    Msg={
        'Type':1,
        'Content':wordsToSend,
        'FromUserName':My["UserName"],
        'ToUserName':ToUserName,
        'LocalID':LocalID,
        'ClientMsgId': LocalID,
        'Scene':0
    }

    params = {
        'BaseRequest': BaseRequest,
        'Msg': Msg,
        'Scene': '0'
    }
    headers = {'content-type': 'application/json; charset=UTF-8'}



    r = myRequests.post(url=url, data=json.dumps(params), headers=headers)
    r.encoding = 'utf-8'
    data = r.json()


    dic = data

    state = responseState('sendMsg', dic['BaseResponse'])
    return state

def sendFakeMsg(fromer,receiver,wordsToSend):  #
    ToUserName=""
    FromUserName=""
    for member in FriendMemberList:
        if not receiver == "":
            if member['NickName'] == receiver:
                ToUserName = member['UserName']
                continue
            if member['PYQuanPin'] == receiver:
                ToUserName = member['UserName']
                continue
            if member['RemarkPYQuanPin'] == receiver:
                ToUserName = member['UserName']
                continue
        if not fromer == "":
            if member['NickName'] == fromer:
                FromUserName = member['UserName']
                continue
            if member['PYQuanPin'] == fromer:
                FromUserName = member['UserName']
                continue
            if member['RemarkPYQuanPin'] == fromer:
                FromUserName = member['UserName']
                continue
    if ToUserName=="":
        print("没找到该好友")
    url = 'https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxsendmsg'
    LocalID='%s%s'%(int(time.time()),'1234567')
    Msg={
        'Type':1,
        'Content':wordsToSend,
        'FromUserName':ToUserName,
        'ToUserName':FromUserName,
        'LocalID':LocalID,
        'ClientMsgId': LocalID
    }

    params = {
        'BaseRequest': BaseRequest,
        'Msg': Msg,
        'Scene': '0'
    }
    headers = {'content-type': 'application/json; charset=UTF-8'}



    r = myRequests.post(url=url, data=json.dumps(params), headers=headers)
    r.encoding = 'utf-8'
    data = r.json()


    dic = data

    state = responseState('sendMsg', dic['BaseResponse'])
    return state

def scheduleSendMsgTask(ScheduleTime,receiver,wordsToSend):
    print '开始创建任务：'
    hms=ScheduleTime.split(':')
    if len(hms)==3:
        curTime = datetime.now()
        desTime = curTime.replace(hour=int(hms[0]), minute=int(hms[1]), second=int(hms[2]), microsecond=0)
        delta = curTime - desTime
        skipSeconds=0
        if delta.total_seconds()>0:
            skipSeconds = 24*60*60 - delta.total_seconds()
        else:
            skipSeconds=0-delta.total_seconds()
        Timer(skipSeconds, sendMsg,(receiver,wordsToSend)).start()
        print '任务创建成功,将于%s秒后执行'%(skipSeconds)
    else:
        print '时间格式不正确，请重新制定任务'

def createChatroom(UserNames):
    MemberList = [{'UserName': UserName} for UserName in UserNames]

    url = (base_uri +
        '/webwxcreatechatroom?pass_ticket=%s&r=%s' % (
            pass_ticket, int(time.time())) )
    params = {
        'BaseRequest': BaseRequest,
        'MemberCount': len(MemberList),
        'MemberList': MemberList,
        'Topic': '',
    }
    headers = {'content-type': 'application/json; charset=UTF-8'}

    r = myRequests.post(url=url, data=json.dumps(params),headers=headers)
    r.encoding = 'utf-8'
    data = r.json()


    dic = data
    ChatRoomName = dic['ChatRoomName']

    state = responseState('createChatroom', dic['BaseResponse'])

    return ChatRoomName

def deleteMember(ChatRoomName, UserNames):
    url = (base_uri +
        '/webwxupdatechatroom?fun=delmember&pass_ticket=%s' % (pass_ticket) )
    params = {
        'BaseRequest': BaseRequest,
        'ChatRoomName': ChatRoomName,
        'DelMemberList': ','.join(UserNames),
    }
    headers = {'content-type': 'application/json; charset=UTF-8'}

    r = myRequests.post(url=url, data=json.dumps(params),headers=headers)
    r.encoding = 'utf-8'
    data = r.json()

    # print(data)

    dic = data

    state = responseState('deleteMember', dic['BaseResponse'])
    return state


def main():
    global myRequests,FriendMemberList
    if hasattr(ssl, '_create_unverified_context'):
        ssl._create_default_https_context = ssl._create_unverified_context
    headers = {
        'User-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/44.0.2403.125 Safari/537.36'}
    myRequests = requests.Session()
    myRequests.headers.update(headers)
    if not getUUID():
        print('获取uuid失败')
        return

    print('正在获取二维码图片...')
    showQRImage()

    while waitForLogin() != '200':
        pass

    os.remove(QRImagePath)

    if not login():
        print '登录失败'
        return

    if not webwxinit():
        print '初始化失败'
        return

    notify()
    FriendMemberList = webwxgetcontact()
    print '你有%d好友,每行展示他的昵称，备注名，后续可输入任一个名字：'%(len(FriendMemberList))
    i=1
    for member in FriendMemberList:
        try:
            #print str(i)+":\t"+member['UserName']+'\t'+member['NickName']+'\t'+member['PYQuanPin']+'\t'+member['RemarkPYQuanPin']
            if member['NickName']=='sunshine' or member['NickName']=='nuinui':
                noRobotList.append(member['UserName'])
            pass
        except:
            pass
        i=i+1

    #获取最近联系人，然后获取群username，继而获取群成员

    #sendMsg('bianzeming','test')

    """
    syncCheck()
    webwxsync()   #开启心跳  获取最近联系人,必须先synccheck
    getqunmember(QunList)
    """
    heartBeatLoop()
    """
    threading.Thread(target=heartBeatLoop).start()



    #拉陌生人入群失败。返回数据包里成功，实际上失败
    tmp=[]
    i=0
    for member in qunMemberList:
        if member in FriendMemberList:
            continue
        tmp.append(member)
        i=i+1
        if i==20:
            break
    createChatroom(tmp)




    #直接伪身份发消息失败
    sendFakeMsg('jaffer','wubo','test from lf')



    #测试拉陌生人进群，失败，UserName每次都变化
    UserNames = []
    UserNames.append('@36fe95eaf54019da680f5ff438457bfd7ba8f1876ace9e33292d4aec209fd60b')
    UserNames.append('@2801585d433a6296f53b4db7c703ecca1aa8d926c177229e08d6f53565c9e4e1')
    ChatRoomName=createChatroom(UserNames)
    deleteMember(ChatRoomName, UserNames)
    """
"""

    print '开始制定任务：'
    while True:
        receiver = raw_input("接受者:")
        content = raw_input("想说的话:")
        when = raw_input("发送时刻(时分秒，以分号隔开):")
        threading.Thread(target=scheduleSendMsgTask,args=(when,receiver,content)).start()
        time.sleep(3)
        print ''
    """


# windows下编码问题修复
# http://blog.csdn.net/heyuxuanzee/article/details/8442718

class UnicodeStreamFilter:

    def __init__(self, target):
        self.target = target
        self.encoding = 'utf-8'
        self.errors = 'replace'
        self.encode_to = self.target.encoding

    def write(self, s):
        if type(s) == str:
            try:
                s = s.decode('utf-8')
            except:
                pass
        s = s.encode(self.encode_to, self.errors).decode(self.encode_to)
        self.target.write(s)

if sys.stdout.encoding == 'cp936':
    sys.stdout = UnicodeStreamFilter(sys.stdout)

if __name__ == '__main__':
    print('my wechat')
    alice.learn("startup.xml")
    alice.respond('LOAD ALICE')
    main()