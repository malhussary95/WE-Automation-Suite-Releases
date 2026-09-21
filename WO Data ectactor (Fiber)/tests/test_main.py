import os
import tempfile
import unittest

import main


class RenamePdfNameTests(unittest.TestCase):
    def test_build_pdf_name_uses_cid_port_order_option_format(self):
        data = {
            "CID": "12345",
            "Port": "2/3",
            "Order Option": "A, B"
        }

        self.assertEqual(
            main.build_pdf_name(data),
            "12345_2_3_A_B.pdf"
        )

    def test_output_path_uses_separate_output_folder(self):
        self.assertEqual(
            main.resolve_output_path("WOs", "sample.pdf"),
            os.path.join("Output", "sample.pdf")
        )


if __name__ == "__main__":
    unittest.main()
