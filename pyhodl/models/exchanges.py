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


""" Analyze transactions in exchanges """

from datetime import datetime

import numpy as np
from hal.streams.pretty_table import pretty_format_table

from pyhodl.config import DATE_TIME_KEY, VALUE_KEY, NAN, \
    DEFAULT_FIAT
from pyhodl.data.balance import parse_balance, save_balance
from pyhodl.models.transactions import Wallet
from pyhodl.utils import datetime_to_str, get_delta_seconds, is_nan


class CryptoExchange:
    """ Exchange dealing with crypto-coins """

    def __init__(self, transactions, exchange_name):
        """
        :param transactions: [] of Transaction
            List of transactions
        """

        self.transactions = transactions
        if not self.transactions:
            raise ValueError("Creating exchange with no past transaction!")
        self.exchange_name = str(exchange_name)

    def get_transactions_count(self):
        """
        :return: int
            Number of transactions
        """

        return len(self.transactions)

    def get_first_transaction(self):
        """
        :return: Transaction
            First transaction done (with respect to time)
        """

        first = self.transactions[0]
        for transaction in self.transactions:
            if transaction.date < first.date:
                first = transaction
        return first

    def get_last_transaction(self):
        """
        :return: Transaction
            Last transaction done (with respect to time)
        """

        last = self.transactions[0]
        for transaction in self.transactions:
            if transaction.date > last.date:
                last = transaction
        return last

    def get_transactions(self, rule):
        """
        :param rule: func
            Evaluate this function on each transaction as a filter
        :return: generator of [] of Transaction
            List of transactions done between the dates
        """

        for transaction in self.transactions:
            if rule(transaction):
                yield transaction

    def build_wallets(self):
        """
        :return: {} of str -> Wallet
            Build a wallet for each currency traded and put trading history
            there
        """

        wallets = {}
        for transaction in self.transactions:
            if transaction.successful:
                # get coins involved
                coin_buy, coin_sell, coin_fee = \
                    transaction.coin_buy, transaction.coin_sell, \
                    transaction.commission.coin if transaction.commission else None

                # update wallets
                for coin in {coin_buy, coin_sell, coin_fee}:
                    if coin and str(coin) != "None":
                        if coin not in wallets:
                            wallets[coin] = Wallet(coin)

                        wallets[coin].add_transaction(transaction)

        return wallets


class Portfolio:
    """ Contains wallets, of also different coins """

    def __init__(self, wallets, portfolio_name=None):
        self.wallets = wallets
        self.portfolio_name = str(portfolio_name) if portfolio_name else None

    def get_transactions_dates(self):
        dates = []
        for wallet in self.wallets:
            dates += wallet.dates()
        return sorted(dates)

    def get_current_balance(self, currency=DEFAULT_FIAT):
        balances = [
            {
                "symbol": wallet.base_currency,
                "balance": wallet.balance(),
                "value": wallet.balance(currency, True)
            }
            for wallet in self.wallets
        ]
        tot_balance = self.sum_total_balance(balances)

        for i, balance in enumerate(balances):  # add price and %
            balances[i]["price"] = \
                float(balance["value"] / balance["balance"]) if \
                    balance["balance"] != 0.0 else 0.0
            balances[i]["percentage"] = \
                100.0 * min(1.0,
                            1.0 * float(balance["value"]) / tot_balance) if \
                    tot_balance != 0.0 else 0.0

        balances = sorted([
            balance for balance in balances if float(balance["balance"]) > 0.0
        ], key=lambda x: x["value"], reverse=True)

        return balances

    @staticmethod
    def get_balances_from_deltas(deltas):
        """
        :param deltas: [] of {}
            List of delta by transaction date
        :return: [] of {}
            List of subtotal balances by transaction date
        """

        if not deltas:
            return []

        deltas = sorted([
            delta for delta in deltas if delta[VALUE_KEY] != NAN
        ], key=lambda x: x[DATE_TIME_KEY])
        balances = [deltas[0]]
        for delta in deltas[1:]:
            balances.append({
                DATE_TIME_KEY: delta[DATE_TIME_KEY],
                VALUE_KEY: balances[-1][VALUE_KEY] + delta[VALUE_KEY]
            })
        return balances

    @staticmethod
    def sum_total_balance(balances):
        """
        :param balances: [] of {}
            List of raw balances
        :return: float
            Total balance (without counting NaN values)
        """

        return sum([
            balance[VALUE_KEY] for balance in balances
            if not is_nan(balance[VALUE_KEY])
        ])

    def get_crypto_fiat_balance(self, currency):
        dates = self.get_transactions_dates()
        crypto_values = np.zeros(len(dates))  # zeros
        fiat_values = np.zeros(len(dates))

        for wallet in self.wallets:
            balances = wallet.get_balance_array_by_date(dates, currency)
            if wallet.is_crypto():
                crypto_values += balances
            else:
                fiat_values += balances
        return dates, crypto_values.tolist(), fiat_values.tolist()

    def show_balance(self, last=None, save_to=None):
        """
        :param save_to: str
            Path to file where to save balance data
        :param last: str
            Path to file where to read balance data
        :return: float
            Total balance
        """

        last = parse_balance(last) if last else None
        balances = self.get_current_balance()
        total = self.sum_total_balance(balances)
        table = [
            [
                str(balance["symbol"]),
                str(balance["balance"]),
                str(balance["value"]) + " $",
                str(balance["price"]) + " $",
                str(balance["percentage"]) + " %",
                str(
                    float(balance["value"]) -
                    float(last[balance["symbol"]]["value"])
                ) + " $" if last and balance["symbol"] in last else "+/- 0 $",
                str(
                    100.0 * (float(balance["value"]) /
                             float(last[balance["symbol"]]["value"]) - 1.0)
                ) + " %" if last and balance["symbol"] in last and float(
                    last[balance["symbol"]]["value"]) != 0.0 else "+/- 0 %"
            ] for balance in balances
        ]
        pretty_table = pretty_format_table(
            [
                "symbol", "balance", "$ value", "$ price per coin", "%",
                "$ delta", "% delta"
            ], table
        )

        now = datetime.now()
        print("As of", now, "you got")
        print(pretty_table)
        print("Total value: ~", total, "$")

        if last:
            last_time = last[DATE_TIME_KEY]
            time_elapsed = get_delta_seconds(now, last_time) / (60.0 * 60.0)
            print("As of last time", datetime_to_str(last_time), "(",
                  time_elapsed, "hours ago):")

            last_total_balance = sum(
                [
                    float(coin["value"])
                    for symbol, coin in last.items() if symbol != DATE_TIME_KEY
                ]
            )
            delta = total - last_total_balance
            percentage = abs(100.0 * (total / last_total_balance - 1.0)) if \
                last_total_balance != 0.0 else 0.0
            if delta >= 0:
                print("+", delta, "$ (+", percentage, "%)")
            else:
                print("-", abs(delta), "$ (-", percentage, "%)")

        if save_to:
            save_balance(balances, save_to, timestamp=now)

        return total
