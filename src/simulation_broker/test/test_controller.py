import random
import unittest

import pydantic
import yaml

from controller import SetupParser
from jschema import query


class SetupParserTestCase(unittest.TestCase):
    settings: query.Setup

    def setUp(self) -> None:
        self.settings = pydantic.parse_obj_as(query.Setup, yaml.safe_load("""
broker:
  type: broker
  details:
    writer:
      endpoint: http://10.102.108.64:8000/job/64391847bf4506190eaf511d
user:
  type: http
  endpoint: http://localhost:8001
  details: {}
evaluation:
  type: http
  endpoint: http://localhost:8002
  details: {}
walking:
  type: http
  endpoint: http://localhost:8003
  details: {}
generator:
  type: http
  endpoint: http://localhost:8004
  details: {}
planner:
  type: planner
  endpoint: http://localhost:8005
  details: {}
toyama_dummy_bike_id:
  type: http
  endpoint: http://localhost:8006
  details: {}
dummy_transit:
  type: http
  endpoint: http://localhost:8007
  details: {}
dummy_ondemand:
  type: http
  endpoint: http://localhost:8008
  details: {}
"""))
        self.parser = SetupParser(self.settings)

    def test_broker(self):
        name, settings = self.parser.broker
        self.assertEqual(name, "broker")
        self.assertEqual(settings.type, "broker")
        self.assertEqual(settings.details.writer.endpoint, self.settings["broker"].details.writer.endpoint)

    def test_planners(self):
        for name, settings in self.parser.planners:
            self.assertEqual(name, "planner")
            self.assertEqual(settings.type, "planner")

    def test_externals(self):
        for _ in range(10):
            temp = list(self.settings.items())
            part = temp[:-3]
            random.shuffle(part)
            temp[:-3] = part
            parser = SetupParser(dict(temp))
            self.assertEqual([name for name, _ in parser.externals], [
                "generator", "walking", "evaluation", "user",
                "toyama_dummy_bike_id", "dummy_transit", "dummy_ondemand",
            ])


if __name__ == '__main__':
    unittest.main()
