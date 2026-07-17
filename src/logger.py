import datetime

class EventLogger:
    def __init__(self, max_logs=100):
        self.logs = []
        self.max_logs = max_logs

    def add_log(self, msg, entity_id=None):
        time_str = datetime.datetime.now().strftime("%H:%M:%S")
        self.logs.append({"time": time_str, "msg": msg, "entity_id": entity_id})
        if len(self.logs) > self.max_logs:
            self.logs.pop(0)
