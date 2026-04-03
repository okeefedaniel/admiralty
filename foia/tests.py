from datetime import date

from django.test import TestCase

from .models import FOIARequest, StatutoryExemption


class FOIARequestModelTest(TestCase):
    def test_create_foia_request(self):
        request = FOIARequest.objects.create(
            request_number='FOIA-2026-001',
            requester_name='John Smith',
            subject='Records related to tax incentives',
            description='Requesting all records...',
            date_received=date(2026, 3, 1),
        )
        self.assertEqual(request.status, FOIARequest.Status.RECEIVED)
        self.assertIn('FOIA-2026-001', str(request))

    def test_create_statutory_exemption(self):
        exemption = StatutoryExemption.objects.create(
            subdivision='1-210(b)(5)(A)',
            label='Trade Secrets',
            statutory_text='Trade secrets, as defined in...',
            citation='Conn. Gen. Stat. 1-210(b)(5)(A)',
        )
        self.assertIn('Trade Secrets', str(exemption))
