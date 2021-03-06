# Copyright 2014, Ansible, Inc.
# Luke Sneeringer <lsneeringer@ansible.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import time
from copy import copy

import click

from six.moves import StringIO

import tower_cli
from tower_cli.api import client
from tower_cli.utils import exceptions as exc

from tests.compat import unittest, mock


class LaunchTests(unittest.TestCase):
    """A set of tests for ensuring that the job resource's launch command
    works in the way we expect.
    """
    def setUp(self):
        self.res = tower_cli.get_resource('job')

    def test_basic_launch(self):
        """Establish that we are able to create a job that doesn't require
        any invocation-time input.
        """
        with client.test_mode as t:
            t.register_json('/job_templates/1/', {
                'id': 1,
                'name': 'frobnicate',
                'related': {'launch': '/job_templates/1/launch/'},
            })
            t.register_json('/job_templates/1/launch/', {}, method='GET')
            t.register_json('/job_templates/1/launch/', {'job': 42},
                            method='POST')
            result = self.res.launch(1)
            self.assertEqual(result, {'changed': True, 'id': 42})

    def test_basic_launch_monitor_option(self):
        """Establish that we are able to create a job that doesn't require
        any invocation-time input, and that monitor is called if requested.
        """
        with client.test_mode as t:
            t.register_json('/job_templates/1/', {
                'id': 1,
                'name': 'frobnicate',
                'related': {'launch': '/job_templates/1/launch/'},
            })
            t.register_json('/job_templates/1/launch/', {}, method='GET')
            t.register_json('/job_templates/1/launch/', {'job': 42},
                            method='POST')
            with mock.patch.object(type(self.res), 'monitor') as monitor:
                result = self.res.launch(1, monitor=True)
                monitor.assert_called_once_with(42, timeout=None)

    def test_extra_vars_at_runtime(self):
        """Establish that if we should be asking for extra variables at
        runtime, that we do.
        """
        with client.test_mode as t:
            t.register_json('/job_templates/1/', {
                'ask_variables_on_launch': True,
                'extra_vars': 'spam: eggs',
                'id': 1,
                'name': 'frobnicate',
                'related': {'launch': '/job_templates/1/launch/'},
            })
            t.register_json('/job_templates/1/launch/', {}, method='GET')
            t.register_json('/job_templates/1/launch/', {'job': 42},
                            method='POST')
            with mock.patch.object(click, 'edit') as edit:
                edit.return_value = '# Nothing.\nfoo: bar'
                result = self.res.launch(1, no_input=False)
                self.assertTrue(
                    edit.mock_calls[0][1][0].endswith('spam: eggs'),
                )
            self.assertEqual(
                json.loads(t.requests[2].body)['extra_vars'],
                'foo: bar',
            )
            self.assertEqual(result, {'changed': True, 'id': 42})

    def test_extra_vars_at_runtime_tower_20(self):
        """Establish that if we should be asking for extra variables at
        runtime, that we do.
        (This test is intended for Tower 2.0 compatibility.)
        """
        with client.test_mode as t:
            t.register_json('/job_templates/1/', {
                'ask_variables_on_launch': True,
                'extra_vars': 'spam: eggs',
                'id': 1,
                'name': 'frobnicate',
                'related': {},
            })
            t.register_json('/jobs/', {'id': 42}, method='POST')
            t.register_json('/jobs/42/start/', {}, method='GET')
            t.register_json('/jobs/42/start/', {}, method='POST')
            with mock.patch.object(click, 'edit') as edit:
                edit.return_value = '# Nothing.\nfoo: bar'
                result = self.res.launch(1, no_input=False)
                self.assertTrue(
                    edit.mock_calls[0][1][0].endswith('spam: eggs'),
                )
            self.assertEqual(
                json.loads(t.requests[1].body)['extra_vars'],
                'foo: bar',
            )
            self.assertEqual(result, {'changed': True, 'id': 42})

    def test_extra_vars_at_call_time(self):
        """Establish that extra variables specified at call time are
        appropriately specified.
        """
        with client.test_mode as t:
            t.register_json('/job_templates/1/', {
                'id': 1,
                'name': 'frobnicate',
                'related': {'launch': '/job_templates/1/launch/'},
            })
            t.register_json('/job_templates/1/launch/', {}, method='GET')
            t.register_json('/job_templates/1/launch/', {'job': 42},
                            method='POST')
            result = self.res.launch(1, extra_vars='foo: bar')

            self.assertEqual(
                json.loads(t.requests[2].body)['extra_vars'],
                'foo: bar',
            )
            self.assertEqual(result, {'changed': True, 'id': 42})

    def test_extra_vars_file_at_call_time(self):
        """Establish that extra variables specified at call time as a file are
        appropriately specified.
        """
        with client.test_mode as t:
            t.register_json('/job_templates/1/', {
                'id': 1,
                'name': 'frobnicate',
                'related': {'launch': '/job_templates/1/launch/'},
            })
            t.register_json('/job_templates/1/launch/', {}, method='GET')
            t.register_json('/job_templates/1/launch/', {'job': 42},
                            method='POST')
            result = self.res.launch(1, extra_vars=StringIO('foo: bar'))

            self.assertEqual(
                json.loads(t.requests[2].body)['extra_vars'],
                'foo: bar',
            )
            self.assertEqual(result, {'changed': True, 'id': 42})

    def test_passwords_needed_at_start(self):
        """Establish that we are able to create a job that doesn't require
        any invocation-time input.
        """
        with client.test_mode as t:
            t.register_json('/job_templates/1/', {
                'id': 1,
                'name': 'frobnicate',
                'related': {'launch': '/job_templates/1/launch/'},
            })
            t.register_json('/job_templates/1/launch/', {
                'passwords_needed_to_start': ['foo'],
            }, method='GET')
            t.register_json('/job_templates/1/launch/', {'job': 42},
                            method='POST')

            with mock.patch('tower_cli.resources.job.getpass') as getpass:
                getpass.return_value = 'bar'
                result = self.res.launch(1)
                getpass.assert_called_once_with('Password for foo: ')
            self.assertEqual(result, {'changed': True, 'id': 42})


class StatusTests(unittest.TestCase):
    """A set of tests to establish that the job status command works in the
    way that we expect.
    """
    def setUp(self):
        self.res = tower_cli.get_resource('job')

    def test_normal(self):
        """Establish that the data about a job retrieved from the jobs
        endpoint is provided.
        """
        with client.test_mode as t:
            t.register_json('/jobs/42/', {
                'elapsed': 1335024000.0,
                'extra': 'ignored',
                'failed': False,
                'status': 'successful',
            })
            result = self.res.status(42)
            self.assertEqual(result, {
                'elapsed': 1335024000.0,
                'failed': False,
                'status': 'successful',
            })
            self.assertEqual(len(t.requests), 1)

    def test_detailed(self):
        with client.test_mode as t:
            t.register_json('/jobs/42/', {
                'elapsed': 1335024000.0,
                'extra': 'ignored',
                'failed': False,
                'status': 'successful',
            })
            result = self.res.status(42, detail=True)
            self.assertEqual(result, {
                'elapsed': 1335024000.0,
                'extra': 'ignored',
                'failed': False,
                'status': 'successful',
            })
            self.assertEqual(len(t.requests), 1)


class MonitorTests(unittest.TestCase):
    """A set of tests to establish that the job monitor command works in the
    way that we expect.
    """
    def setUp(self):
        self.res = tower_cli.get_resource('job')

    def test_already_successful(self):
        """Establish that if we attempt to monitor an already successful job,
        we simply get back the job success report.
        """
        with client.test_mode as t:
            t.register_json('/jobs/42/', {
                'elapsed': 1335024000.0,
                'failed': False,
                'status': 'successful',
            })
            with mock.patch.object(time, 'sleep') as sleep:
                result = self.res.monitor(42)
                self.assertEqual(sleep.call_count, 0)
        self.assertEqual(result['status'], 'successful')

    def test_failure(self):
        """Establish that if the job has failed, that we raise the
        JobFailure exception.
        """
        with client.test_mode as t:
            t.register_json('/jobs/42/', {
                'elapsed': 1335024000.0,
                'failed': True,
                'status': 'failed',
            })
            with self.assertRaises(exc.JobFailure):
                with mock.patch.object(click, 'secho') as secho:
                    with mock.patch('tower_cli.models.base.is_tty') as tty:
                        tty.return_value = True
                        result = self.res.monitor(42)
                self.assertTrue(secho.call_count >= 1)

    def test_failure_non_tty(self):
        """Establish that if the job has failed, that we raise the
        JobFailure exception, and also don't print bad things on non-tty
        outfiles.
        """
        with client.test_mode as t:
            t.register_json('/jobs/42/', {
                'elapsed': 1335024000.0,
                'failed': True,
                'status': 'failed',
            })
            with self.assertRaises(exc.JobFailure):
                with mock.patch.object(click, 'echo') as echo:
                    with mock.patch('tower_cli.models.base.is_tty') as tty:
                        tty.return_value = False
                        result = self.res.monitor(42)
                self.assertTrue(echo.call_count >= 1)

    def test_monitoring(self):
        """Establish that if the first status call returns a pending job,
        and the second a success, that both calls are made, and a success
        finally returned.
        """
        # Set up our data object.
        data = {'elapsed': 1335024000.0, 'failed': False, 'status': 'pending'}

        # Register the initial request's response.
        with client.test_mode as t:
            t.register_json('/jobs/42/', copy(data))

            # Create a way to assign a successful data object to the request.
            def assign_success(*args):
                t.clear()
                t.register_json('/jobs/42/', dict(data, status='successful'))

            # Make the successful state assignment occur when time.sleep()
            # is called between requests.
            with mock.patch.object(time, 'sleep') as sleep:
                sleep.side_effect = assign_success
                with mock.patch.object(click, 'secho') as secho:
                    with mock.patch('tower_cli.models.base.is_tty') as tty:
                        tty.return_value = True
                        result = self.res.monitor(42, min_interval=0.21)
                self.assertTrue(secho.call_count >= 100)

            # We should have gotten two requests total, to the same URL.
            self.assertEqual(len(t.requests), 2)
            self.assertEqual(t.requests[0].url, t.requests[1].url)

    def test_timeout(self):
        """Establish that the --timeout flag is honored if sent to
        `tower-cli job monitor`.
        """
        # Set up our data object.
        # This doesn't have to change; it will always be pending
        # (thus the timeout).
        data = {'elapsed': 1335024000.0, 'failed': False, 'status': 'pending'}

        # Mock out the passage of time.
        with client.test_mode as t:
            t.register_json('/jobs/42/', copy(data))
            with mock.patch.object(click, 'secho') as secho:
                with self.assertRaises(exc.Timeout):
                    with mock.patch('tower_cli.models.base.is_tty') as tty:
                        tty.return_value = True
                        result = self.res.monitor(42, min_interval=0.21,
                                                      timeout=0.1)
                self.assertTrue(secho.call_count >= 1)

    def test_monitoring_not_tty(self):
        """Establish that the monitor command prints more useful output
        for logging if not connected to a tty.
        """
        # Set up our data object.
        data = {'elapsed': 1335024000.0, 'failed': False, 'status': 'pending'}

        # Register the initial request's response.
        with client.test_mode as t:
            t.register_json('/jobs/42/', copy(data))

            # Create a way to assign a successful data object to the request.
            def assign_success(*args):
                t.clear()
                t.register_json('/jobs/42/', dict(data, status='successful'))

            # Make the successful state assignment occur when time.sleep()
            # is called between requests.
            with mock.patch.object(time, 'sleep') as sleep:
                sleep.side_effect = assign_success
                with mock.patch.object(click, 'echo') as echo:
                    with mock.patch('tower_cli.models.base.is_tty') as tty:
                        tty.return_value = False
                        result = self.res.monitor(42, min_interval=0.21)
                self.assertTrue(echo.call_count >= 1)

            # We should have gotten two requests total, to the same URL.
            self.assertEqual(len(t.requests), 2)
            self.assertEqual(t.requests[0].url, t.requests[1].url)


class CancelTests(unittest.TestCase):
    """A set of tasks to establish that the job cancel command works in the
    way that we expect.
    """
    def setUp(self):
        self.res = tower_cli.get_resource('job')

    def test_standard_cancelation(self):
        """Establish that a standard cancelation command works in the way
        we expect.
        """
        with client.test_mode as t:
            t.register('/jobs/42/cancel/', '', method='POST')
            result = self.res.cancel(42)
            self.assertTrue(t.requests[0].url.endswith('/jobs/42/cancel/'))
            self.assertTrue(result['changed'])

    def test_cancelation_completed(self):
        """Establish that a standard cancelation command works in the way
        we expect.
        """
        with client.test_mode as t:
            t.register('/jobs/42/cancel/', '', method='POST', status_code=405)
            result = self.res.cancel(42)
            self.assertTrue(t.requests[0].url.endswith('/jobs/42/cancel/'))
            self.assertFalse(result['changed'])

    def test_cancelation_completed_with_error(self):
        """Establish that a standard cancelation command works in the way
        we expect.
        """
        with client.test_mode as t:
            t.register('/jobs/42/cancel/', '', method='POST', status_code=405)
            with self.assertRaises(exc.TowerCLIError):
                result = self.res.cancel(42, fail_if_not_running=True)
