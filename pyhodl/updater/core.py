# !/usr/bin/python3
# coding: utf_8

# Copyright 2017-2018 Stefano Fogarollo
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


""" Updates exchange transactions """

import os
import threading
from datetime import datetime, timedelta

from pyhodl.apis.exchanges import ApiManager
from pyhodl.app import ConfigManager
from pyhodl.config import DATA_FOLDER
from pyhodl.updater.updaters import ExchangeUpdater
from pyhodl.utils import get_actual_class_name, parse_datetime, datetime_to_str

UPDATE_CONFIG = os.path.join(
    DATA_FOLDER,
    "config.json"
)


class UpdateManager(ConfigManager):
    """ Manages config for Updater """

    def __init__(self):
        ConfigManager.__init__(self, UPDATE_CONFIG)

        self.last_update = None

    def is_time_to_update(self):
        return datetime.now() > self.time_next_update()

    def time_next_update(self):
        return self.time_last_update() + self.update_interval()

    def time_last_update(self):
        if self.last_update:
            return self.last_update

        try:
            return parse_datetime(self.get("last_update"))
        except:
            return datetime.fromtimestamp(0)  # no record

    def update_interval(self):
        raw = self.get("interval")
        tokens = ["s", "m", "h", "d", "w"]
        time_token = 0.0
        for tok in tokens:
            if raw.endswith(tok):
                time_token = float(raw.split(tok)[0])

        if raw.endswith("s"):
            return timedelta(seconds=time_token)
        elif raw.endswith("m"):
            return timedelta(minutes=time_token)
        elif raw.endswith("h"):
            return timedelta(hours=time_token)
        elif raw.endswith("d"):
            return timedelta(days=time_token)
        elif raw.endswith("w"):
            return timedelta(days=7 * time_token)
        else:
            raise ValueError("Cannot parse update interval", raw)

    def save_time_update(self):
        self.last_update = datetime.now()
        self.data["last_update"] = datetime_to_str(self.last_update)
        self.save()

    def get_data_folder(self):
        try:
            folder = self.get("folder")
            os.stat(folder)
        except:
            folder = DATA_FOLDER

        if not os.path.exists(folder):
            os.makedirs(folder)

        return folder


class Updater:
    """ Updates exchanges local data """

    def __init__(self, config_file, verbose):
        self.manager = UpdateManager()
        self.api_manager = ApiManager(config_file=config_file)
        self.api_updaters = []
        self.verbose = verbose

        self._build_updaters()

    def run(self):
        interval = self.manager.update_interval().total_seconds()
        threading.Timer(interval, self.run).start()

        if self.verbose:
            print("Updating local data...")

        for updater in self.api_updaters:
            try:
                updater.update(self.verbose)
            except Exception as e:
                print("Cannot update", get_actual_class_name(updater),
                      "due to", e)

        self.manager.save_time_update()
        print("Next update:", datetime_to_str(self.manager.time_next_update()))

    def _build_updaters(self):
        for api in self.api_manager.get_all():
            try:
                updater = ExchangeUpdater.build_updater(
                    api.get_client(), DATA_FOLDER
                )
                self.api_updaters.append(updater)
                print("Successfully authenticated client",
                      get_actual_class_name(api))
            except Exception as e:
                print("Cannot authenticate client",
                      get_actual_class_name(api), "due to", e)
