import asyncio
import base64
import io
import logging
import os
from pathlib import Path
import shlex
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'files/data/scripts'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from control_security import admin_auth, ensure_admin_token
from recovery import browser_command, supervise_process, recover_connection, reachable, OFFLINE_URL
from hardening_install import revoke_legacy_key
from install_config import LEGACY_SSH_PUBLIC_KEY
from install_reviewed import validate_commit
from hardening_install import configure_network


class IntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_routes_auth_post_methods_and_private_config(self):
        import config
        from mod_webserver import WebServer
        with tempfile.TemporaryDirectory() as folder, patch.object(config, 'CONFIG_FOLDER', Path(folder)):
            conf=config.Config(Mock())
            server=WebServer(Mock(),conf,Mock(listener=None),Mock())
            self.assertEqual(server.bind_ip,'127.0.0.1')
            server.schedule_restart_services=Mock()
            app=web.Application(middlewares=[admin_auth('x'*43)])
            server.setup_routes(app)
            client=TestClient(TestServer(app))
            await client.start_server()
            headers={'Authorization':'Basic '+base64.b64encode(('admin:'+'x'*43).encode()).decode(),'X-WallThing-Action':'1'}
            try:
                self.assertEqual((await client.get('/getconfig')).status,401)
                for route in ['/maintenance?action=Reboot%20Superbird','/simulatekey?key=1']:
                    self.assertEqual((await client.get(route,headers=headers)).status,405)
                self.assertEqual((await client.post('/simulatekey?key=1',headers=headers)).status,503)
                fields={key: 'on' if value is True else str(value) for key,value in conf.config.items() if value is not False}
                fields['url']='https://example.org/new'
                response=await client.post('/setconfig',headers=headers,data=fields,allow_redirects=False)
                self.assertEqual(response.status,302)
                self.assertEqual(config.Config(Mock()).get('url'),'https://example.org/new')
                self.assertEqual(conf.config_file.stat().st_mode & 0o777,0o600)
            finally:
                await client.close()
                server.loop.close()

    async def test_kiosk_starts_without_home_assistant(self):
        import kiosk
        config=Mock();config.get.return_value=False
        with patch.object(kiosk,'Config',return_value=config), patch.object(kiosk,'Buttons') as buttons, patch.object(kiosk,'Chromium') as browser, patch.object(kiosk,'WebServer'), patch.object(kiosk.signal,'signal'):
            app=kiosk.App(Mock())
            app.shutdown_pending.set()
            with self.assertRaises(SystemExit) as outcome: app.start()
            self.assertEqual(outcome.exception.code,0)
            buttons.return_value.start.assert_not_called()
            browser.return_value.start.assert_called_once()


class ProvisioningTests(unittest.TestCase):
    def test_firewall_migration_preserves_unrelated_rules_and_is_idempotent(self):
        unrelated=('nat','PREROUTING','-p','tcp','--dport','12345','-j','ACCEPT')
        legacy=('nat','PREROUTING','-p','tcp','-i','wlan0','--dport','80','-j','DNAT','--to-destination','192.168.7.2:80')
        rules={unrelated,legacy};mutations=[]
        def key(args): return (args[2],args[4],*args[5:])
        def check(args,**kwargs): return Mock(returncode=0 if key(args) in rules else 1)
        def execute(args,**kwargs):
            if args[0]=='iptables-save': return
            self.assertIn(args[3],['-A','-D'])
            mutations.append(args)
            if args[3]=='-A': rules.add(key(args))
            else: rules.remove(key(args))
        with tempfile.TemporaryDirectory() as folder:
            configure_network('192.168.7',execute,check,str(Path(folder)/'rules'))
            self.assertIn(unrelated,rules);self.assertNotIn(legacy,rules)
            first_count=len(mutations)
            configure_network('192.168.7',execute,check,str(Path(folder)/'rules'))
            self.assertEqual(len(mutations),first_count)
            self.assertTrue(any(rule[-1]=='REJECT' for rule in rules))

    def test_logs_and_vnc_password_are_not_executable_html(self):
        from page_renderer import PageRenderer
        renderer=PageRenderer(Mock(),Mock(),80,Mock())
        self.assertNotIn('<script>',renderer.colorize_content('<script>alert(1)</script>'))
        renderer.config.get.return_value='</script><script>alert(1)</script>'
        content=renderer.get_content_novncscript()
        self.assertEqual(content.count('</script>'),1)
        self.assertIn('\\u003c/script>',content)

    def test_ha_requests_have_finite_timeouts(self):
        from ha_manager import BoundedSession
        with patch('requests.Session.request') as request:
            BoundedSession().get('https://example.org')
            self.assertEqual(request.call_args.kwargs['timeout'],(3,5))


class AuthTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.token='x'*43
        app=web.Application(middlewares=[admin_auth(self.token)])
        async def success(request): return web.Response(text='ok')
        app.router.add_get('/',success)
        app.router.add_post('/setconfig',success)
        self.client=TestClient(TestServer(app))
        await self.client.start_server()
        self.headers={'Authorization':'Basic '+base64.b64encode(('admin:'+self.token).encode()).decode()}
    async def asyncTearDown(self): await self.client.close()
    async def test_admin_requires_credentials(self):
        self.assertEqual((await self.client.get('/')).status,401)
        self.assertEqual((await self.client.get('/',headers={'Authorization':'Basic broken'})).status,401)
        self.assertEqual((await self.client.get('/',headers=self.headers)).status,200)
    async def test_write_requires_same_origin_or_explicit_cli_header(self):
        self.assertEqual((await self.client.post('/setconfig',headers=self.headers)).status,403)
        headers={**self.headers,'Origin':'https://malicious.invalid'}
        self.assertEqual((await self.client.post('/setconfig',headers=headers)).status,403)
        headers={**self.headers,'Origin':str(self.client.make_url('/')).rstrip('/')}
        self.assertEqual((await self.client.post('/setconfig',headers=headers)).status,200)
        headers={**self.headers,'X-WallThing-Action':'1'}
        self.assertEqual((await self.client.post('/setconfig',headers=headers)).status,200)
    async def test_cross_site_and_cache_protection(self):
        self.assertEqual((await self.client.get('/',headers={**self.headers,'Sec-Fetch-Site':'cross-site'})).status,403)
        response=await self.client.get('/',headers=self.headers)
        self.assertEqual(response.headers['Cache-Control'],'no-store')
        self.assertEqual(response.headers['X-Frame-Options'],'DENY')


class CredentialTests(unittest.TestCase):
    def test_generated_token_is_private_and_persistent(self):
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/'token'
            token=ensure_admin_token(file)
            self.assertGreaterEqual(len(token),32)
            self.assertEqual(token,ensure_admin_token(file))
            self.assertEqual(file.stat().st_mode & 0o777,0o600)
    def test_revocation_preserves_other_keys_and_refuses_lockout(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'authorized_keys'
            path.write_text(LEGACY_SSH_PUBLIC_KEY+'\n')
            with self.assertRaises(RuntimeError): revoke_legacy_key(path)
            self.assertIn(LEGACY_SSH_PUBLIC_KEY,path.read_text())
            path.write_text(LEGACY_SSH_PUBLIC_KEY+'\nssh-ed25519 unique host\n')
            revoke_legacy_key(path)
            self.assertEqual(path.read_text(),'ssh-ed25519 unique host\n')
    def test_commit_requires_exact_revision(self):
        self.assertEqual(validate_commit('a'*40),'a'*40)
        for value in ['main','HEAD','a'*39,'a'*40+'; reboot']:
            with self.assertRaises(ValueError): validate_commit(value)


class RecoveryTests(unittest.TestCase):
    def test_browser_arguments_remain_literal_and_nonroot(self):
        args=['--app=https://example.org/?q=$(touch /tmp/nope)&x="hi"']
        command=browser_command('/usr/bin/chromium',args)
        self.assertEqual(shlex.split(shlex.join(command)),command)
        self.assertIn('wallthing-browser',command)
        self.assertNotIn('--no-sandbox',command)
    def test_restart_is_bounded(self):
        stopped=Mock();stopped.is_set.return_value=False;stopped.wait.return_value=False
        process=Mock();process.poll.return_value=1
        spawn=Mock(return_value=process);fatal=Mock()
        supervise_process(['browser'],stopped,io.StringIO(),Mock(),popen=spawn,clock=lambda:10,fatal=fatal)
        self.assertEqual(spawn.call_count,5);fatal.assert_called_once_with(1)
        self.assertEqual([call.args[0] for call in stopped.wait.call_args_list],[2,4,8,16])
    def test_clean_stop_does_not_restart(self):
        stopped=threading.Event();stopped.set();spawn=Mock()
        supervise_process([],stopped,None,Mock(),popen=spawn)
        spawn.assert_not_called()
    def test_offline_and_reconnect(self):
        stopped=Mock();stopped.wait.side_effect=[False]*4+[True]
        browser=Mock();browser.config.get.return_value='https://example.org'
        recover_connection(browser,stopped,check=Mock(side_effect=[False,False,False,True]))
        self.assertEqual([c.args[0] for c in browser.chromium_navigate.call_args_list],[OFFLINE_URL,'https://example.org'])
    def test_http_probe_handles_login_and_server_error(self):
        for status,want in [(200,True),(302,True),(401,True),(503,False)]:
            response=Mock(status_code=status);get=Mock(return_value=response)
            self.assertEqual(reachable('https://example.org',get),want)
            response.close.assert_called_once()
        self.assertFalse(reachable('file:///etc/passwd'))
    def test_ha_connect_returns_without_waiting_for_server(self):
        import ha_manager
        config=Mock();config.get.side_effect=lambda k: {'ha_server':'https://example.org','ha_token':'token'}[k]
        manager=ha_manager.HAManager(config,Mock())
        with patch.object(threading.Thread,'start') as start:
            manager.start();start.assert_called_once()
        manager.stop();self.assertTrue(manager.stopped.is_set())


if __name__=='__main__': unittest.main()
