import numpy as np
from datetime import datetime, time
from appdaemon.plugins.hass.hassapi import Hass

STATE_UNKNOWN = 'unknown'

class TwoDayPriceClassification(Hass):
    def initialize(self):
        # Schedule the update method to run every hour
        self.run_hourly(self.update, time(minute=0, second=0))
        
        # Schedule the check_tomorrow_valid method to run every few minutes starting from 13:00
        self.check_tomorrow_valid_handle = self.run_minutely(self.check_tomorrow_valid, time(hour=13, minute=0, second=0))
        
        # Call the update method at the start
        self.update({})

    def relative_classification(self, today_prices, tomorrow_prices):
        # Check if today's prices and tomorrow's prices are different
        if np.array_equal(today_prices, tomorrow_prices):
            self.log("Today's prices and tomorrow's prices are the same. Skipping update for this hour.")
            return

        # Calculate the difference between today's and tomorrow's prices
        price_difference = np.array(today_prices) - np.array(tomorrow_prices)
        # Round down to two decimal places
        price_difference = np.floor(price_difference * 100) / 100
        # Set the state of the sensor
        hourly_data_relative = {f"{hour:02d}:00-{(hour+1)%24:02d}:00": value for hour, value in enumerate(price_difference.tolist())}
        current_hour_value = hourly_data_relative.get(f"{datetime.now().hour:02d}:00-{(datetime.now().hour+1)%24:02d}:00", STATE_UNKNOWN)
        attributes = {**hourly_data_relative, 'current_hour': current_hour_value}
        self.set_state('sensor.Electricity_TwoDay_classification_relative', state=current_hour_value, attributes=attributes)

    def dynamic_classification(self, today_prices, tomorrow_prices):
        # Calculate the difference between today's and tomorrow's prices
        price_difference = np.array(tomorrow_prices) - np.array(today_prices)
        # Classify the prices based on whether they are increasing or decreasing
        classified_prices_dynamic = ["increasing" if change > 0 else "decreasing" for change in price_difference]
        # Set the state of the sensor
        hourly_data_dynamic = {f"{hour:02d}:00-{(hour+1)%24:02d}:00": value for hour, value in enumerate(classified_prices_dynamic)}
        current_hour_value = hourly_data_dynamic.get(f"{datetime.now().hour:02d}:00-{(datetime.now().hour+1)%24:02d}:00", STATE_UNKNOWN)
        attributes = {**hourly_data_dynamic, 'current_hour': current_hour_value}
        self.set_state('sensor.Electricity_TwoDay_classification_dynamic', state=current_hour_value, attributes=attributes)

    def weighted_classification(self, today_prices, tomorrow_prices):
        # Define the weights for today's and tomorrow's prices
        weights = [0.5, 0.5]  # This means both today's and tomorrow's prices have equal weight
        # Calculate the weighted average of today's and tomorrow's prices
        classified_prices_weighted = np.average([today_prices, tomorrow_prices], axis=0, weights=weights)
        # Round down to two decimal places
        classified_prices_weighted = np.floor(classified_prices_weighted * 100) / 100
        # Set the state of the sensor
        hourly_data_weighted = {f"{hour:02d}:00-{(hour+1)%24:02d}:00": value for hour, value in enumerate(classified_prices_weighted.tolist())}
        current_hour_value = hourly_data_weighted.get(f"{datetime.now().hour:02d}:00-{(datetime.now().hour+1)%24:02d}:00", STATE_UNKNOWN)
        attributes = {**hourly_data_weighted, 'current_hour': current_hour_value}
        self.set_state('sensor.Electricity_TwoDay_classification_weighted', state=current_hour_value, attributes=attributes)

    def binned_classification(self, today_prices, tomorrow_prices=None):
        # If tomorrow's prices are available, concatenate today's and tomorrow's prices
        if tomorrow_prices is not None:
            prices = np.concatenate((today_prices, tomorrow_prices))
        # If tomorrow's prices are not available, use today's prices
        else:
            prices = np.array(today_prices)
        # Round down to two decimal places
        prices = np.floor(prices * 100) / 100
        # Divide the prices into 7 bins based on the range of the prices
        bins = np.linspace(min(prices), max(prices) + 0.01, 8)  # Add a small buffer to the maximum value
        # Classify the prices based on which bin they fall into
        classified_prices_binned_today = np.digitize(today_prices, bins)  # Classes from 1 to 7
        classified_prices_binned_tomorrow = np.digitize(tomorrow_prices, bins) if tomorrow_prices is not None else []
        return classified_prices_binned_today, classified_prices_binned_tomorrow

        # Set the state of the sensor with timeslots as keys and class levels as values
        date_str_today = datetime.now().strftime("%Y%m%d")
        date_str_tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
        hourly_data_binned_today = {f"{date_str_today} {hour:02d}:00-{(hour+1)%24:02d}:00": f"Class {value}" for hour, value in enumerate(classified_prices_binned_today.tolist())}
        hourly_data_binned_tomorrow = {f"{date_str_tomorrow} {hour:02d}:00-{(hour+1)%24:02d}:00": f"Class {value}" for hour, value in enumerate(classified_prices_binned_tomorrow.tolist())} if classified_prices_binned_tomorrow is not None else {}
        current_hour_value = hourly_data_binned_today.get(f"{date_str_today} {datetime.now().hour:02d}:00-{(datetime.now().hour+1)%24:02d}:00", STATE_UNKNOWN)
        attributes = {**hourly_data_binned_today, **hourly_data_binned_tomorrow}
        self.set_state('sensor.Electricity_TwoDay_classification', state=current_hour_value, attributes=attributes)
    
    def check_tomorrow_valid(self, kwargs):
        # Fetch tomorrow's prices from the sensor
        tomorrow_prices_partial = self.get_state('sensor.nordpool_kwh_se4_sek_3_10_025', attribute='tomorrow')
        self.log(f"Tomorrow's prices: {tomorrow_prices_partial}")  # Added logging for tomorrow's prices

        # Check if the prices are valid
        tomorrow_valid = tomorrow_prices_partial is not None and tomorrow_prices_partial != 'unknown'
        self.log(f"Are tomorrow's prices valid? {tomorrow_valid}")  # Added logging for validity check

        # If tomorrow's prices are valid, call the update method and cancel the check_tomorrow_valid method
        if tomorrow_valid:
            self.update({})
            self.cancel_timer(self.check_tomorrow_valid_handle)
            self.check_tomorrow_valid_handle = None
            self.log("Timer successfully cancelled")


    def update(self, kwargs):
        # Fetch today's and tomorrow's prices from the sensor
        today_prices = self.get_state('sensor.nordpool_kwh_se4_sek_3_10_025', attribute='today')
        tomorrow_prices = self.get_state('sensor.nordpool_kwh_se4_sek_3_10_025', attribute='tomorrow')

        self.log(f"Today's prices: {today_prices}")
        self.log(f"Tomorrow's prices: {tomorrow_prices}")

        # Check if the prices are valid
        today_valid = today_prices is not None and today_prices != 'unknown'
        tomorrow_valid = tomorrow_prices is not None and tomorrow_prices != 'unknown'

        # If today's prices are not valid, return without doing anything
        if not today_valid:
            return

        # Convert today's prices from string to float and replace 'unknown' with np.nan
        today_prices = [float(price) if price != 'unknown' else np.nan for price in today_prices]

        # If tomorrow's prices are valid and the current time is after 13:00, use them in the calculations
        if tomorrow_valid and datetime.now().hour >= 13:
            tomorrow_prices = [float(price) if price != 'unknown' else np.nan for price in tomorrow_prices]
        else:
            tomorrow_prices = None

        # Call the classification methods with today's and tomorrow's prices
        binned_classes_today, binned_classes_tomorrow = self.binned_classification(today_prices, tomorrow_prices)

        # Set the state of the sensor with only the current hour's binned class
        date_str = datetime.now().strftime("%Y-%m-%d")
        hourly_data_binned_today = {f"{date_str} {hour:02d}:00-{(hour+1)%24:02d}:00": f"Class {value}" for hour, value in enumerate(binned_classes_today)}

        if tomorrow_prices is not None:
            date_str_tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
            hourly_data_binned_tomorrow = {f"{date_str_tomorrow} {hour:02d}:00-{(hour+1)%24:02d}:00": f"Class {value}" for hour, value in enumerate(binned_classes_tomorrow)}
            hourly_data_binned = {**hourly_data_binned_today, **hourly_data_binned_tomorrow}
        else:
            hourly_data_binned = hourly_data_binned_today

        current_hour_value = hourly_data_binned.get(f"{date_str} {datetime.now().hour:02d}:00-{(datetime.now().hour+1)%24:02d}:00", STATE_UNKNOWN)
        attributes = {**hourly_data_binned}
        self.set_state('sensor.Electricity_TwoDay_classification', state=current_hour_value, attributes=attributes)
        