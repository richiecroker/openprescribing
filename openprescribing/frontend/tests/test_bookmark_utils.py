from dateutil.relativedelta import relativedelta
import unittest

from django.test import TestCase
import base64
from datetime import datetime
from http.server import BaseHTTPRequestHandler
from http.server import HTTPServer
import socket
from threading import Thread
import requests
from django.core.mail import EmailMultiAlternatives
from django.conf import settings

from frontend.models import ImportLog
from frontend.models import Measure
from frontend.models import MeasureValue
from frontend.models import PCT
from frontend.models import Practice
from frontend.views import bookmark_utils


class IntroTextTest(unittest.TestCase):
    def test_nothing(self):
        stats = _makeContext(possible_top_savings_total=9000.1)
        msg = bookmark_utils.getIntroText(stats, 'CCG')
        self.assertIn("We've no new information about this CCG", msg)

    def test_worst(self):
        stats = _makeContext(worst=[None])
        msg = bookmark_utils.getIntroText(stats, 'CCG')
        self.assertNotIn("We've no new information about this CCG", msg)
        self.assertIn("We've found one prescribing measure where this "
                      "CCG <span class='worse'>could be doing better", msg)

    def test_worst_plural(self):
        stats = _makeContext(worst=[None, None])
        msg = bookmark_utils.getIntroText(stats, 'CCG')
        self.assertIn("We've found two prescribing measures where this "
                      "CCG <span class='worse'>could be doing better", msg)

    def test_decline_plural(self):
        stats = _makeContext(declines=[None, None])
        msg = bookmark_utils.getIntroText(stats, 'CCG')
        self.assertIn("We've found two prescribing measures where this "
                      "CCG <span class='worse'>is getting worse", msg)

    def test_decline_and_worse(self):
        stats = _makeContext(declines=[None], worst=[None])
        msg = bookmark_utils.getIntroText(stats, 'thing')
        self.assertIn("We've found two prescribing measures where this "
                      "thing <span class='worse'>is getting worse, "
                      "or could be doing better", msg)

    def test_improvement(self):
        stats = _makeContext(improvements=[None])
        msg = bookmark_utils.getIntroText(stats, 'thing')
        self.assertIn("We've found one prescribing measure where this "
                      "thing <span class='better'>is improving", msg)

    def test_improvement_and_best(self):
        stats = _makeContext(improvements=[None], best=[None])
        msg = bookmark_utils.getIntroText(stats, 'thing')
        self.assertIn("We've found two prescribing measures where this "
                      "thing <span class='better'>is doing well", msg)

    def test_decline_and_improvement(self):
        stats = _makeContext(declines=[None], improvements=[None])
        msg = bookmark_utils.getIntroText(stats, 'thing')
        self.assertIn("We've found one prescribing measure where this "
                      "thing <span class='worse'>is getting worse</span>, "
                      "and one measure where it <span class='better'>is "
                      "improving", msg)

    def test_possible_savings(self):
        stats = _makeContext(possible_savings=[None])
        msg = bookmark_utils.getIntroText(stats, 'thing')
        self.assertIn("We've also found one prescribing measure where there "
                      "are some potential cost savings", msg)


class TestRemoveJagged(unittest.TestCase):
    def _makeSome(self, percentiles):
        m = Measure(is_percentage=False)
        return [MeasureValue(percentile=percentile, measure=m)
                for percentile in percentiles]

    def _makeSomeWithPercentCalcValues(self, percentiles):
        m = Measure(is_percentage=True)
        return [MeasureValue(measure=m,
                             percentile=percentile,
                             calc_value=value)
                for percentile, value in percentiles]

    def _makeSomeWithNumeratorValues(self, percentiles):
        m = Measure(is_percentage=False)
        return [MeasureValue(measure=m, percentile=percentile, numerator=value)
                for percentile, value in percentiles]

    def test_percentiles_at_extremes_one_extreme_ok(self):
        vals = [(5, 0.9), (6, 1.0), (4, 0.8)]
        filtered = bookmark_utils.remove_jagged(
            self._makeSomeWithPercentCalcValues(vals))
        self.assertEqual(
            len(filtered), len(vals))

    def test_percentiles_at_extremes_two_extremes_bad(self):
        vals = [(5, 0.9), (6, 1.0), (4, 0.0)]
        filtered = bookmark_utils.remove_jagged(
            self._makeSomeWithPercentCalcValues(vals))
        self.assertNotEqual(
            len(filtered), len(vals))

    def test_non_percentiles_extremes(self):
        vals = [5, 5, 5, 5, 5, 5, 5, 0, 0]
        filtered = bookmark_utils.remove_jagged(
            self._makeSome(vals))
        self.assertNotEqual(
            len(filtered), len(vals))

    def test_non_percentiles_no_low_numerators(self):
        vals = [(5, 30), (6, 20), (4, 30)]
        filtered = bookmark_utils.remove_jagged(
            self._makeSomeWithNumeratorValues(vals))
        self.assertEqual(
            len(filtered), len(vals))

    def test_non_percentiles_with_low_numerators(self):
        vals = [(5, 10), (6, 12), (4, 30)]
        filtered = bookmark_utils.remove_jagged(
            self._makeSomeWithNumeratorValues(vals))
        self.assertNotEqual(
            len(filtered), len(vals))

    def test_very_jagged(self):
        vals = [1, 100, 1, 100, 1, 50, 40, 100]
        filtered = bookmark_utils.remove_jagged(self._makeSome(vals))
        self.assertNotEqual(
            len(filtered), len(vals))

    @unittest.skip('should be fixed by better algorithm')
    def test_low_not_jagged(self):
        vals = [0, 1, 0, 1, 0, 1, 0, 1]
        filtered = bookmark_utils.remove_jagged(self._makeSome(vals))
        self.assertEqual(
            len(filtered), len(vals))

    def test_low_not_jagged_not_zero(self):
        vals = [1, 2, 1, 2, 1, 2, 1, 2]
        filtered = bookmark_utils.remove_jagged(self._makeSome(vals))
        self.assertEqual(
            len(filtered), len(vals))

    def test_quite_jagged(self):
        vals = [0, 100, 0, 50, 10, 20, 100]
        filtered = bookmark_utils.remove_jagged(self._makeSome(vals))
        self.assertNotEqual(
            len(filtered), len(vals))

    def test_slightly_jagged(self):
        vals = [30, 70, 50, 60, 50, 40, 10]
        filtered = bookmark_utils.remove_jagged(self._makeSome(vals))
        self.assertEqual(
            len(filtered), len(vals))

    def test_not_at_all_jagged(self):
        vals = [40, 50, 60, 70, 80]
        filtered = bookmark_utils.remove_jagged(self._makeSome(vals))
        self.assertEqual(
            len(filtered), len(vals))


class TestBookmarkUtilsPerforming(TestCase):
    fixtures = ['bookmark_alerts', 'measures']

    def setUp(self):
        self.measure_id = 'cerazette'
        self.measure = Measure.objects.get(pk=self.measure_id)
        self.measure.low_is_good = True
        self.measure.save()
        pct = PCT.objects.get(pk='03V')
        practice_with_high_percentiles = Practice.objects.get(pk='P87629')
        practice_with_low_percentiles = Practice.objects.get(pk='P87630')
        ImportLog.objects.create(
            category='prescribing',
            current_at=datetime.today())
        for i in range(3):
            month = datetime.today() + relativedelta(months=i)
            MeasureValue.objects.create(
                measure=self.measure,
                practice=None,
                pct=pct,
                percentile=95,
                month=month
            )
            MeasureValue.objects.create(
                measure=self.measure,
                practice=practice_with_high_percentiles,
                pct=pct,
                percentile=95,
                month=month
            )
            MeasureValue.objects.create(
                measure=self.measure,
                practice=practice_with_low_percentiles,
                pct=pct,
                percentile=5,
                month=month
            )
        self.pct = pct
        self.high_percentile_practice = practice_with_high_percentiles
        self.low_percentile_practice = practice_with_low_percentiles

    # Worst performing
    # CCG bookmarks
    def test_hit_where_ccg_worst_in_specified_number_of_months(self):
        finder = bookmark_utils.InterestingMeasureFinder(
            pct=self.pct)
        worst_measures = finder.worst_performing_in_period(3)
        self.assertIn(self.measure, worst_measures)

    def test_miss_where_not_better_in_specified_number_of_months(self):
        self.measure.low_is_good = False
        self.measure.save()
        finder = bookmark_utils.InterestingMeasureFinder(
            pct=self.pct)
        worst_measures = finder.worst_performing_in_period(3)
        self.assertFalse(worst_measures)

    def test_miss_where_not_enough_global_data(self):
        finder = bookmark_utils.InterestingMeasureFinder(
            pct=self.pct)
        worst_measures = finder.worst_performing_in_period(6)
        self.assertFalse(worst_measures)

    def test_miss_where_not_worst_in_specified_number_of_months(self):
        MeasureValue.objects.all().delete()
        finder = bookmark_utils.InterestingMeasureFinder(
            pct=self.pct)
        worst_measures = finder.worst_performing_in_period(3)
        self.assertFalse(worst_measures)

    # Practice bookmarks
    def test_hit_where_practice_worst_in_specified_number_of_months(self):
        finder = bookmark_utils.InterestingMeasureFinder(
            practice=self.high_percentile_practice)
        worst_measures = finder.worst_performing_in_period(3)
        self.assertIn(self.measure, worst_measures)

    # Best performing
    def test_hit_where_practice_best_in_specified_number_of_months(self):
        finder = bookmark_utils.InterestingMeasureFinder(
            practice=self.low_percentile_practice)
        best_measures = finder.best_performing_in_period(3)
        self.assertIn(self.measure, best_measures)


class TestBookmarkUtilsChanging(TestCase):
    fixtures = ['bookmark_alerts', 'measures']

    def setUp(self):
        self.measure_id = 'cerazette'
        self.measure = Measure.objects.get(pk=self.measure_id)
        ImportLog.objects.create(
            category='prescribing',
            current_at=datetime.today())
        practice_with_high_change = Practice.objects.get(pk='P87629')
        practice_with_high_neg_change = Practice.objects.get(pk='P87631')
        practice_with_low_change = Practice.objects.get(pk='P87630')
        for i in range(3):
            month = datetime.today() + relativedelta(months=i)
            MeasureValue.objects.create(
                measure=self.measure,
                practice=practice_with_high_change,
                percentile=(i+1) * 7,
                month=month
            )
            MeasureValue.objects.create(
                measure=self.measure,
                practice=practice_with_high_neg_change,
                percentile=(3-i) * 7,
                month=month
            )
            MeasureValue.objects.create(
                measure=self.measure,
                practice=practice_with_low_change,
                percentile=i+1,
                month=month
            )
        self.practice_with_low_change = practice_with_low_change
        self.practice_with_high_change = practice_with_high_change
        self.practice_with_high_neg_change = practice_with_high_neg_change

    def test_low_change_not_returned(self):
        finder = bookmark_utils.InterestingMeasureFinder(
            practice=self.practice_with_low_change,
            interesting_percentile_change=10
        )
        self.assertEqual(finder.most_change_in_period(3),
                         {'improvements': [],
                          'declines': []})

    def test_high_change_returned(self):
        finder = bookmark_utils.InterestingMeasureFinder(
            practice=self.practice_with_high_change,
            interesting_percentile_change=10)
        sorted_measure = finder.most_change_in_period(3)
        measure_info = sorted_measure['improvements'][0]
        self.assertEqual(
            measure_info[0].id, 'cerazette')
        self.assertAlmostEqual(
            measure_info[1], 7)   # start
        self.assertAlmostEqual(
            measure_info[2], 21)  # end
        self.assertAlmostEqual(
            measure_info[3], 0)   # residuals

    def test_high_negative_change_returned(self):
        finder = bookmark_utils.InterestingMeasureFinder(
            practice=self.practice_with_high_neg_change,
            interesting_percentile_change=10)
        sorted_measure = finder.most_change_in_period(3)
        measure_info = sorted_measure['declines'][0]
        self.assertEqual(
            measure_info[0].id, 'cerazette')
        self.assertAlmostEqual(
            measure_info[1], 21)  # start
        self.assertAlmostEqual(
            measure_info[2], 7)   # end
        self.assertAlmostEqual(
            measure_info[3], 0)   # residuals


def _makeCostSavingMeasureValues(measure, practice, savings):
    """Create measurevalues for the given practice and measure with
    savings at the 50th centile taken from the specified `savings`
    array.  Savings at the 90th centile are set as 100 times those at
    the 50th, and at the 10th as 0.1 times.

    """
    for i in range(len(savings)):
        month = datetime.today() + relativedelta(months=i)
        MeasureValue.objects.create(
            measure=measure,
            practice=practice,
            percentile=0.5,
            cost_savings={
                '10': savings[i] * 0.1,
                '50': savings[i],
                '90': savings[i] * 100, },
            month=month
        )


class TestBookmarkUtilsSavingsPossible(TestCase):
    fixtures = ['bookmark_alerts', 'measures']

    def setUp(self):
        self.measure_id = 'cerazette'
        self.measure = Measure.objects.get(pk=self.measure_id)
        ImportLog.objects.create(
            category='prescribing',
            current_at=datetime.today())
        self.practice = Practice.objects.get(pk='P87629')
        _makeCostSavingMeasureValues(
            self.measure, self.practice, [0, 1500, 2000])

    def test_possible_savings(self):
        finder = bookmark_utils.InterestingMeasureFinder(
            practice=self.practice)
        savings = finder.top_and_total_savings_in_period(3)
        self.assertEqual(savings['possible_savings'], [(self.measure, 3500)])
        self.assertEqual(savings['achieved_savings'], [])
        self.assertEqual(savings['possible_top_savings_total'], 350000)

    def test_possible_savings_low_is_good(self):
        self.measure.low_is_good = True
        self.measure.save()
        finder = bookmark_utils.InterestingMeasureFinder(
            practice=self.practice)
        savings = finder.top_and_total_savings_in_period(3)
        self.assertEqual(savings['possible_savings'], [(self.measure, 3500)])
        self.assertEqual(savings['achieved_savings'], [])
        self.assertEqual(savings['possible_top_savings_total'], 350.0)


class TestBookmarkUtilsSavingsAchieved(TestCase):
    fixtures = ['bookmark_alerts', 'measures']

    def setUp(self):
        self.measure_id = 'cerazette'
        self.measure = Measure.objects.get(pk=self.measure_id)
        ImportLog.objects.create(
            category='prescribing',
            current_at=datetime.today())
        self.practice = Practice.objects.get(pk='P87629')
        _makeCostSavingMeasureValues(
            self.measure, self.practice, [-1000, -500, 100])

    def test_achieved_savings(self):
        finder = bookmark_utils.InterestingMeasureFinder(
            practice=self.practice)
        savings = finder.top_and_total_savings_in_period(3)
        self.assertEqual(savings['possible_savings'], [])
        self.assertEqual(savings['achieved_savings'], [(self.measure, 1400)])
        self.assertEqual(savings['possible_top_savings_total'], 10000)


class MockServerRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/page.html':
            self.send_response(requests.codes.ok)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            response_content = """
            <html>
            <head><script src='/jquery.min.js'></script></head>
            <div id='thing1'>This is thing 1</div>
            <div id='thing2'>This is thing 2</div>
            """
            self.wfile.write(response_content)
            return
        elif self.path == '/jquery.min.js':
            self.send_response(requests.codes.ok)
            self.send_header('Content-Type', 'text/javascript')
            self.end_headers()
            with open(settings.SITE_ROOT + '/media/js/'
                      'node_modules/jquery/dist/jquery.min.js', 'r') as f:
                self.wfile.write(f.read())
                return


def get_free_port():
    s = socket.socket(socket.AF_INET, type=socket.SOCK_STREAM)
    s.bind(('localhost', 0))
    address, port = s.getsockname()
    s.close()
    return port


def start_mock_server(port):
    mock_server = HTTPServer(('localhost', port), MockServerRequestHandler)
    mock_server_thread = Thread(target=mock_server.serve_forever)
    mock_server_thread.setDaemon(True)
    mock_server_thread.start()


class GenerateImageTestCase(unittest.TestCase):
    def test_image_generated(self):
        port = get_free_port()
        start_mock_server(port)
        msg = EmailMultiAlternatives(
            "Subject", "body", "sender@email.com", ["recipient@email.com"])
        url = ":%s/page.html" % port
        file_path = "/tmp/image.png"
        selector = "#thing2"
        self.assertEqual(len(msg.attachments), 0)
        image = bookmark_utils.attach_image(msg, url, file_path, selector)
        with open(
                settings.SITE_ROOT + '/frontend/tests/fixtures/'
                'alert-email-image.png', 'rb') as expected:
            self.assertEqual(len(msg.attachments), 1)
            attachment = msg.attachments[0]
            # Check the attachment is as we expect
            self.assertEqual(attachment.get_filename(), 'image.png')
            self.assertIn(image, attachment['Content-ID'])
            # Attachments in emails are base64 *with line breaks*, so
            # we remove those.
            self.assertEqual(
                attachment.get_payload().replace("\n", ""),
                base64.b64encode(expected.read()))


def _makeContext(**kwargs):
    empty_context = {
        'most_changing': {
            'declines': [
            ],
            'improvements': [
            ]
        },
        'top_savings': {
            'possible_top_savings_total': 0.0,
            'possible_savings': [],
            'achieved_savings': []
        },
        'worst': [
        ],
        'best': [
        ]
    }
    if 'declines' in kwargs:
        empty_context['most_changing']['declines'] = kwargs['declines']
    if 'improvements' in kwargs:
        empty_context['most_changing']['improvements'] = (
            kwargs['improvements'])
    if 'possible_top_savings_total' in kwargs:
        empty_context['top_savings']['possible_top_savings_total'] = (
            kwargs['possible_top_savings_total'])
    if 'possible_savings' in kwargs:
        empty_context['top_savings']['possible_savings'] = (
            kwargs['possible_savings'])
    if 'achieved_savings' in kwargs:
        empty_context['top_savings']['achieved_savings'] = (
            kwargs['achieved_savings'])
    if 'worst' in kwargs:
        empty_context['worst'] = kwargs['worst']
    if 'best' in kwargs:
        empty_context['best'] = kwargs['best']
    return empty_context
