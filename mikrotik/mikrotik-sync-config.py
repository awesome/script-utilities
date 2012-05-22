#!/usr/bin/env python

#                                                                                                                                                                                   
# Copyright (c) 2012 CodePill Sp. z o.o.
# Author: Krzysztof Ksiezyk <kksiezyk@gmail.com>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES
# OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
# IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
# NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF
# THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

# ----------------------------------------
# define functions
def clprint(color,txt,nonl=False):
    if nocolor:
        if nonl:
            print txt,
        else:
            print txt
        return

    colours={
        'default':'',
        'yellow': '\x1b[01;33m',
        'blue': '\x1b[01;34m',
        'cyan': '\x1b[01;36m',
        'green': '\x1b[01;32m',
        'red': '\x1b[01;31m'
    }
    if nonl:
        print colours[color]+txt+'\x1b[00m',
    else:
        print colours[color]+txt+'\x1b[00m'
# -----------------------
def myexit(code=0):
    os.remove(mt_config_main)
    os.remove(mt_config_back_new)  
    os.remove(mt_config_back_before)  
    os.remove(mt_config_back_after)  
    sys.exit(code)
# ----------------------------------------

# init
import ConfigParser, os, sys, re, time, warnings

warnings.filterwarnings("ignore", category=RuntimeWarning)

# parse config
config = ConfigParser.RawConfigParser()
config.read(__file__[:-3]+'.cfg')

rtr_main=config.get('settings','rtr_main')
rtr_back=config.get('settings','rtr_back')
rtr_back_ident=config.get('settings','rtr_back_ident')
rtr_back_standby_interface=config.get('settings','rtr_back_standby_interface')
ssh_user=config.get('settings','ssh_user')
ssh_key_file=config.get('settings','ssh_key_file')
backup_mode_script=config.get('settings','backup_mode_script')
exclude=config.get('settings','exclude').split(',')
exclude.append('metarouter')
exclude.append('port')
exclude.append('user')
exclude.append('system routerboard')
exclude.append('system identity')
nocolor='--nocolor' in sys.argv

skip=False

mt_config_main=os.tmpnam()
mt_config_back_new=os.tmpnam()
mt_config_back_before=os.tmpnam()
mt_config_back_after=os.tmpnam()

clprint('green', 'Start: '+time.strftime("%Y-%m-%d %H:%M:%S"))
clprint('green', 'Checking main router identity')
current_ident=os.popen('/usr/bin/ssh -i '+ssh_key_file+' '+ssh_user+'@'+rtr_main+' ":put [ /system identity get name ]"').read().strip()
if current_ident.lower().startswith(rtr_back_ident):
    clprint ('red','Main router ('+rtr_main+') ident is the same as ident of backup router ('+rtr_back+') - '+rtr_back_ident)
    myexit(255)    

clprint('green', 'Checking DHCP client on backup router')
res=os.popen('/usr/bin/ssh -i '+ssh_key_file+' '+ssh_user+'@'+rtr_back+' ":put [ /ip dhcp-client get '+rtr_back_standby_interface+' disabled ]"').read()
if not res.lower().startswith("false"):
    clprint ('yellow','\tCan\'t find DHCP client running on standby interface ['+rtr_back_standby_interface+']')

clprint('green', 'Checking backup mode script and its scheduler on backup router')
res=os.popen('/usr/bin/ssh -i '+ssh_key_file+' '+ssh_user+'@'+rtr_back+' ":put [ /system script get [/system script find name='+backup_mode_script+' ] name ]"').read()
if not res.lower().startswith(backup_mode_script):
    clprint ('yellow','\tCan\'t find script '+backup_mode_script)
res=os.popen('/usr/bin/ssh -i '+ssh_key_file+' '+ssh_user+'@'+rtr_back+' ":put [ /system scheduler get [/system scheduler find name='+backup_mode_script+' ] disabled ]"').read()
if res.lower().startswith("false"):
    clprint ('green', 'Disabling scheduler for '+backup_mode_script)
    res=os.system('/usr/bin/ssh -i '+ssh_key_file+' '+ssh_user+'@'+rtr_back+' "/system scheduler set '+backup_mode_script+' disabled=yes"')  
    if not res==0:
        clprint ('red','Command returned error code '+str(res))
        myexit(255)
elif not res.lower().startswith("true"):
    clprint ('yellow','\tCan\'t find scheduler for script '+backup_mode_script)

clprint('green', 'Comparing user list')
users_main=os.popen('/usr/bin/ssh -i '+ssh_key_file+' '+ssh_user+'@'+rtr_main+' "/user print value-list " | grep name:').read().strip()
users_back=os.popen('/usr/bin/ssh -i '+ssh_key_file+' '+ssh_user+'@'+rtr_back+' "/user print value-list " | grep name:').read().strip()
users_main=re.split(" +",users_main[6:])
users_back=re.split(" +",users_back[6:])
users_to_add=[user for user in users_main if user not in users_back]
users_to_del=[user for user in users_back if user not in users_main]
if len(users_to_add):
    clprint('yellow','\tUsers to add on backup router: '+', '.join(users_to_add))
if len(users_to_del):
    clprint('yellow','\tUsers to del backup router: '+', '.join(users_to_add))
    
clprint('green', 'Creating erase configuration commands for backup router')
out=open(mt_config_back_new,'w')

# to do - add erases for /routing bgp etc. / hotspot / smb / mpls
out.write(":foreach element in=[ /interface find type=vlan ] do={ :put [ /interface vlan remove $element ] }\n")
out.write(":foreach element in=[ /interface find type=pptp-out ] do={ :put [ /interface pptp-client remove $element ] }\n")
out.write(":foreach element in=[ /interface find type=pptp-in ] do={ :put [ /interface pptp-server remove $element ] }\n")
out.write(":foreach element in=[ /interface find type=pppoe-out ] do={ :put [ /interface pppoe-client remove $element ] }\n")
out.write(":foreach element in=[ /interface find type=pppoe-in ] do={ :put [ /interface pppoe-server remove $element ] }\n")
if 'interface wireless' not in exclude:
    out.write(":foreach element in=[ /interface wireless security-profiles find default=no ] do={ :put [ /interface wireless security-profiles remove $element ] }\n")
out.write(":foreach element in=[ /ip hotspot profile find default=no ] do={ :put [ /ip hotspot profile remove $element ] }\n")
out.write(":foreach element in=[ /ip hotspot user profile find default=no ] do={ :put [ /ip hotspot user profile remove $element ] }\n")
out.write(":foreach element in=[ /ip ipsec proposal find default=no ] do={ :put [ /ip ipsec proposal remove $element ] }\n")
out.write(":foreach element in=[ /ip pool find ] do={ :put [ /ip pool remove $element ] }\n")
out.write(":foreach element in=[ /ip dhcp-server find ] do={ :put [ /ip dhcp-server remove $element ] }\n")
out.write(":foreach element in=[ /ppp profile find default=no ] do={ :put [ /ppp profile remove $element ] }\n")
out.write(":foreach element in=[ /queue type find default=no ] do={ :put [ /queue type remove $element ] }\n")
out.write(":foreach element in=[ /queue simple find ] do={ :put [ /queue simple remove $element ] }\n")
out.write(":foreach element in=[ /snmp community find default=no ] do={ :put [ /snmp community remove $element ] }\n")
out.write(":foreach element in=[ /system logging find default=no ] do={ :put [ /system logging remove $element ] }\n")
out.write(":foreach element in=[ /system logging action find default=no ] do={ :put [ /system logging action remove $element ] }\n")
out.write(":foreach element in=[ /user group find default=no ] do={ :put [ /user group remove $element ] }\n")
out.write(":foreach element in=[ /ip address find dynamic=no ] do={ :put [ /ip address remove $element ] }\n")
out.write(":foreach element in=[ /ip dhcp-server lease find ] do={ :put [ /ip dhcp-server lease remove $element ] }\n")
out.write(":foreach element in=[ /ip dhcp-server network find ] do={ :put [ /ip dhcp-server network remove $element ] }\n")
for subsection in 'address-list','filter','mangle','nat':
    out.write(":foreach element in=[ /ip firewall "+subsection+" find ] do={ :put [ /ip firewall "+subsection+" remove $element ] }\n")
out.write(":foreach element in=[ /ip route find static=yes ] do={ :put [ /ip route remove $element ] }\n")
out.write(":foreach element in=[ /ppp secret find ] do={ :put [ /ppp secret remove $element ] }\n")
for subsection in 'interface','resource','queue':
    out.write(":foreach element in=[ /tool graphing "+subsection+" find ] do={ :put [ /tool graphing "+subsection+" remove $element ] }\n")
out.write(":foreach element in=[ /system script find name!="+backup_mode_script+" ] do={ :put [ /system script remove $element ] }\n")
out.write(":foreach element in=[ /system scheduler find name!="+backup_mode_script+" ] do={ :put [ /system scheduler remove $element ] }\n")
out.write("\n")

clprint('green', 'Adding firewall rules for standby interface to configuration script')
out.write("/ip firewall filter add chain=input in-interface="+rtr_back_standby_interface+" action=accept comment=\"# ALLOW ALL TRAFFIC THROUGH MANAGEMENT INTERFACE #\"\n")
out.write("/ip firewall filter add chain=output out-interface="+rtr_back_standby_interface+" action=accept comment=\"# ALLOW ALL TRAFFIC THROUGH MANAGEMENT INTERFACE #\"\n")
out.write("\n")

clprint('green', 'Getting main router ('+rtr_main+') compact config')
res=os.system('/usr/bin/ssh -i '+ssh_key_file+' '+ssh_user+'@'+rtr_main+' "/export compact" 1>'+mt_config_main+' 2>/dev/null')
if not res==0:
    clprint ('red','Command returned error code '+str(res))
    myexit(255)    

clprint('green', 'Filtering config')
cnt=1
for line in open(mt_config_main,'r').readlines():
    line=line.strip()
    if re.match('^\/', line):
        skip=False
        for ex in exclude:
            if re.match('^\/'+ex+' ',line+' ',re.IGNORECASE): skip=True
        if skip: clprint('yellow','\t- skipping section '+line)
        else: out.write(":put "+str(cnt)+"\n")

    if skip: continue
    out.write(line+"\n")
    cnt+=1

out.write("\n")
out.write("/file remove update-config-script.rsc\n")
out.write("\n")
out.write(":log info \"Configuration updated\"\n")

out.close()

clprint('green', 'Uploading config to backup router ('+rtr_back+')')
res=os.system('/usr/bin/scp -i '+ssh_key_file+' '+mt_config_back_new+' '+ssh_user+'@'+rtr_back+':update-config-script.rsc 1>/dev/null 2>/dev/null')
if not res==0:
    clprint ('red','Command returned error code '+str(res))
    myexit(255)

clprint('green', 'Backuping current backup router configuration')
res=os.system('/usr/bin/ssh -i '+ssh_key_file+' '+ssh_user+'@'+rtr_back+' "/system backup save name=backup_before_sync_'+time.strftime("%Y%m%d_%H%M%S")+'" 1>/dev/null 2>/dev/null')
if not res==0:
    clprint ('red','Command returned error code '+str(res))
    myexit(255)    

clprint('green', 'Getting backup router current config')
res=os.system('/usr/bin/ssh -i '+ssh_key_file+' '+ssh_user+'@'+rtr_back+' "/export compact" 1>'+mt_config_back_before+' 2>/dev/null')
if not res==0:
    clprint ('red','Command returned error code '+str(res))
    myexit(255)    

clprint('green', 'Running configuration script')
res=os.popen('/usr/bin/ssh -i '+ssh_key_file+' '+ssh_user+'@'+rtr_back+' "/import update-config-script.rsc" | tail -n1').read().strip()
if not res.lower().startswith("script file loaded and executed successfully"):
    clprint ('red','Command returned message "'+str(res)+'"')
    myexit(255)    

clprint ('green', 'Running '+backup_mode_script+' script')
res=os.system('/usr/bin/ssh -i '+ssh_key_file+' '+ssh_user+'@'+rtr_back+' "/system script run '+backup_mode_script+'" 1>/dev/null 2>/dev/null')  
if not res==0:
    clprint ('red','Command returned error code '+str(res))
    myexit(255)

clprint ('green', 'Enabling scheduler for '+backup_mode_script)
res=os.system('/usr/bin/ssh -i '+ssh_key_file+' '+ssh_user+'@'+rtr_back+' "/system scheduler set '+backup_mode_script+' disabled=no" 1>/dev/null 2>/dev/null')  
if not res==0:
    clprint ('red','Command returned error code '+str(res))
    myexit(255)

clprint('green', 'Getting backup router new config')
res=os.system('/usr/bin/ssh -i '+ssh_key_file+' '+ssh_user+'@'+rtr_back+' "/export compact" 1>'+mt_config_back_after+' 2>/dev/null')
if not res==0:
    clprint ('red','Command returned error code '+str(res))
    myexit(255)    

clprint('green', 'Comparing configs')
clprint('green', '-----------------------------------------------------------------------')
res=os.system('diff '+mt_config_back_before+' '+mt_config_back_after)
clprint('green', '-----------------------------------------------------------------------')


