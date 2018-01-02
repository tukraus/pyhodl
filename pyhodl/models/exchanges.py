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
from pyhodl.app import DATE_TIME_KEY, VALUE_KEY, FIAT_COINS
from pyhodl.data.coins import Coin
from pyhodl.models.transactions import Wallet


class CryptoExchange:
    """ Exchange dealing with crypto-coins """

    TIME_INTERVALS = {
        "1h": 1,
        "1d": 24,
        "7d": 24 * 7,
        "30d": 24 * 30,
        "3m": 24 * 30 * 3,
        "6m": 24 * 30 * 6,
        "1y": 24 * 365
    }  # interval -> hours
    OUTPUT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

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

    def get_balance_values(self, currency):
        crypto_deltas = []
        fiat_deltas = []
        for wallet in self.wallets:
            deltas = list(wallet.get_delta_balance_by_transaction())
            equivalents = [
                {
                    DATE_TIME_KEY: delta["transaction"].date,
                    VALUE_KEY: wallet.get_equivalent(
                        delta["transaction"].date,
                        currency,
                        delta[VALUE_KEY]
                    )
                } for delta in deltas
            ]

            if Coin(wallet.base_currency) in FIAT_COINS:
                fiat_deltas += equivalents
                print(wallet.base_currency, "to fiats")
            else:
                crypto_deltas += equivalents
                print(wallet.base_currency, "to cryptos")

        all_deltas = sorted(all_deltas, key=lambda x: x[DATE_TIME_KEY])
        all_balances = [all_deltas[0]]
        for delta in all_deltas[1:]:
            all_balances.append({
                DATE_TIME_KEY: delta[DATE_TIME_KEY],
                VALUE_KEY: all_balances[-1][VALUE_KEY] + delta[VALUE_KEY]
            })
        return all_balances

    def get_current_balance(self):
        balances = [
            {
                "symbol": wallet.base_currency,
                "balance": wallet.balance(),
                "value": wallet.get_balance_equivalent_now()
            }
            for wallet in self.wallets
        ]
        balances = sorted([
            balance for balance in balances if float(balance["balance"]) > 0.0
        ], key=lambda x: x["value"], reverse=True)
        table = [
            [
                str(balance["symbol"]),
                str(balance["balance"]),
                str(balance["value"]) + " $",
                str(float(balance["value"] / float(balance["balance"]))) + " $"
            ]
            for balance in balances
        ]

        tot_balance = sum([balance["value"] for balance in balances])
        return table, tot_balance
