import unittest
from unittest import mock

from network import doctor

PA = {"npi": "1", "name": "Maria Lopez", "credential": "PA", "specialty": "General Practice", "city": "Miami Beach", "state": "FL"}
NEURO_HIT = {"url": "https://www.humana.com/finder/maria-raquel-lopez", "title": "Dr. Maria Raquel Lopez - Miami, FL - Epilepsy Neurology",
             "content": "Maria Raquel Lopez, MD. Epilepsy Neurology. Humana Gold Plus 2026 provider directory."}
GP_HIT = {"url": "https://www.humana.com/finder/maria-lopez-pa", "title": "Maria Lopez, PA - Miami Beach, FL - General Practice",
          "content": "Maria Lopez, PA. General Practice. Humana 2026 provider directory."}


def run(hits, specialty="General Practice", city="Miami Beach"):
    with mock.patch.object(doctor, "find_doctor", return_value=[PA]), mock.patch.object(doctor, "_tavily", return_value=hits):
        return doctor.check("Maria Lopez", "Florida", city, ["Humana"], specialty=specialty)["plans"][0]


class SamePersonTest(unittest.TestCase):
    def test_other_specialty_with_middle_name_is_not_evidence(self):
        self.assertEqual(run([NEURO_HIT])["status"], "no_evidence_found")

    def test_matching_specialty_is_evidence(self):
        self.assertEqual(run([NEURO_HIT, GP_HIT])["status"], "listed_online")

    def test_specialty_taken_from_registry_when_not_passed(self):
        self.assertEqual(run([NEURO_HIT], specialty=None, city=None)["status"], "no_evidence_found")
        self.assertEqual(run([GP_HIT], specialty=None, city=None)["status"], "listed_online")

    def test_spec_words(self):
        self.assertEqual(doctor._spec_words("General Practice"), ["general"])
        self.assertEqual(doctor._spec_words("Internal Medicine"), ["internal"])


if __name__ == "__main__":
    unittest.main()
