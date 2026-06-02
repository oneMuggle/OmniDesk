"""Sensor management business logic: inventory and calibration."""

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers


class InventoryService:
    """Sensor movement (check-in/check-out) processing."""

    @staticmethod
    def process_movement(movement) -> None:
        """Process a new sensor movement and update inventory."""
        with transaction.atomic():
            sensor = movement.sensor
            quantity = movement.quantity

            if movement.movement_type == "in":
                sensor.current_quantity += quantity
                sensor.status = "in_stock"
            elif movement.movement_type == "out":
                if sensor.current_quantity < quantity:
                    raise serializers.ValidationError("出库数量不能大于当前库存数量。")
                sensor.current_quantity -= quantity
                sensor.status = "retired" if sensor.current_quantity == 0 else "in_use"

            sensor.save()

    @staticmethod
    def update_movement(old_instance, new_instance) -> None:
        """Recalculate inventory when a movement record is updated."""
        with transaction.atomic():
            sensor = new_instance.sensor
            old_quantity = old_instance.quantity
            new_quantity = new_instance.quantity
            old_type = old_instance.movement_type
            new_type = new_instance.movement_type

            # Revert old quantity effect
            if old_type == "in":
                sensor.current_quantity -= old_quantity
            elif old_type == "out":
                sensor.current_quantity += old_quantity

            # Apply new quantity effect
            if new_type == "in":
                sensor.current_quantity += new_quantity
            elif new_type == "out":
                if sensor.current_quantity < new_quantity:
                    raise serializers.ValidationError("出库数量不能大于当前库存数量。")
                sensor.current_quantity -= new_quantity

            # Update status
            if sensor.current_quantity == 0:
                sensor.status = "retired"
            elif new_type == "in":
                sensor.status = "in_stock"
            elif new_type == "out":
                sensor.status = "in_use"

            sensor.save()


class CalibrationService:
    """Calibration reminder management."""

    @staticmethod
    def mark_as_sent(reminder) -> dict:
        """Mark a calibration reminder as sent."""
        if not reminder.is_sent:
            reminder.is_sent = True
            reminder.sent_date = timezone.now()
            reminder.save()
            return {"status": "reminder marked as sent", "is_sent": True}
        return {"status": "reminder already sent", "is_sent": True}
