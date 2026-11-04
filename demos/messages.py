"""The three scripted demo messages. Expected bands are in expected.json."""

LEGITIMATE = (
    "Our campus internship is unpaid. Apply on the company careers page. "
    "There is no fee."
)
OBVIOUS_SCAM = (
    "Congratulations, you are selected. Pay the registration fee today only. "
    "Guaranteed internship. Do not share this. Send your bank account number. Act now. "
    "Apply at http://microsoft.secure-login.tk/offer"
)
SUBTLE = (
    "Tata Consultancy Services internship. Kindly pay the joining fee to confirm your seat. "
    "Apply at https://secure-login.tk/offer"
)

DEMOS = (
    {"id": "legitimate", "text": LEGITIMATE},
    {"id": "obvious_scam", "text": OBVIOUS_SCAM},
    {"id": "subtle", "text": SUBTLE},
)


def email_source(text: str, kind: str) -> str:
    if kind == "obvious_scam":
        return f"""From: "Campus Placement" <offers@gmail.com>
To: student@college.edu
Reply-To: cash@yahoo.com
Subject: You are selected. Pay today
Authentication-Results: mx.example;
    spf=fail smtp.mailfrom=gmail.com;
    dkim=fail header.i=@gmail.com;
    dmarc=fail header.from=gmail.com
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="BOUND"

--BOUND
Content-Type: text/plain; charset="utf-8"

{text}

--BOUND
Content-Type: application/pdf
Content-Disposition: attachment; filename="offer.pdf.exe"

not-executed
--BOUND--
"""
    if kind == "subtle":
        return f"""From: "TCS Careers" <hr@secure-login.tk>
To: student@college.edu
Reply-To: hr@secure-login.tk
Subject: Kindly confirm your internship seat
Authentication-Results: mx.example; spf=none; dkim=none; dmarc=none
Content-Type: text/plain; charset="utf-8"

{text}
"""
    return f"""From: Recruiting <jobs@careers.example.com>
To: student@college.edu
Reply-To: jobs@careers.example.com
Subject: Campus internship next steps
Authentication-Results: mx.example; spf=pass; dkim=pass; dmarc=pass
Content-Type: text/plain; charset="utf-8"

{text}
"""
