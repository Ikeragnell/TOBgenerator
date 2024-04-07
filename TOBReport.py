import re
import datetime
import enum 
import shutil
import os
from PyPDF2 import PdfReader, PdfWriter
from io import BytesIO
from reportlab.pdfgen.canvas import Canvas
from PIL import Image
from py_epc_qr.transaction import consumer_epc_qr  

from config import *

class TaxType(enum.Enum):
    LOW = '0.12%'
    MID = '0.35%'
    HIGH = '1.32%'

    @classmethod
    def fromString(cls, strValue):
        for enumMember in cls:
            if enumMember.value == strValue:
                return enumMember
        return None

class TradeRepublicTaxReport:
    def __init__(self, filePath):
        self.filePath = filePath

        file = open(filePath, "rb")
        reader = PdfReader(file)
        pageStr = reader.pages[0].extract_text()

        self._extractMonthYear(pageStr)
        self._extractBaseTax(reader)

    def _extractMonthYear(self, pageStr):
        monthYearPattern = r'(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER) (\d{4})'
        monthYear = re.search(monthYearPattern, pageStr).group(0).split(" ")
        self.month = datetime.datetime.strptime(monthYear[0], '%B').month
        self.year = int(monthYear[1])
    
    def _extractBaseTax(self, reader):
        self.taxType2BaseTax = {TaxType.LOW : [0.0, 0.0], TaxType.MID : [0.0, 0.0], TaxType.HIGH: [0.0, 0.0]}
        taxTypes =  self.taxType2BaseTax.keys()
        pageIdx = 1
        while taxTypes and pageIdx < len(reader.pages):
            pageStr = reader.pages[pageIdx].extract_text()
            taxTypePattern = r'({}|{}|{})'.format(*[taxtype.value for taxtype in self.taxType2BaseTax.keys()])
            taxTypeMatch = re.search(taxTypePattern, pageStr)
            if not taxTypeMatch:
                pageIdx += 1
                continue
            else:
                taxType = TaxType.fromString(taxTypeMatch.group(0))
                totalBaseMatch = re.search('TOTAL TAX BASIS IN EUR: (\d*\.\d*)', pageStr)
                totalTaxMatch = re.search('TOTAL TAX AMOUNT IN EUR: (\d*\.\d*)', pageStr)
                while not totalBaseMatch and not totalTaxMatch:
                    if pageIdx >= len(reader.pages):
                        raise Exception("No total found")
                    pageIdx += 1
                    pageStr = reader.pages[pageIdx].extract_text()
                    totalBaseMatch = re.search('TOTAL TAX BASIS IN EUR: (\d*\.\d*)', pageStr)
                    totalTaxMatch = re.search('TOTAL TAX AMOUNT IN EUR: (\d*\.\d*)', pageStr)
                self.taxType2BaseTax[taxType][0] += float(totalBaseMatch.group(1))
                self.taxType2BaseTax[taxType][1] += float(totalTaxMatch.group(1))
                pageIdx += 1

class TOBReport:
    def __init__(self, traRepTaxReps):
        self.NN = NN
        self.firstName = FIRST_NAME
        self.lastName = LAST_NAME
        self.address = ADDRESS

        self._checkValidity(traRepTaxReps)
        self.traRepTaxReps = traRepTaxReps

        self.taxType2BaseTax = {TaxType.LOW : [0.0, 0.0], TaxType.MID : [0.0, 0.0], TaxType.HIGH: [0.0, 0.0]}
        self.totalTax = 0.0
        for taxRep in self.traRepTaxReps:
            for taxType in TaxType:
                for i in range(len(taxRep.taxType2BaseTax[taxType])):
                    self.taxType2BaseTax[taxType][i] += taxRep.taxType2BaseTax[taxType][i]
                    if i == 1:
                        self.totalTax += taxRep.taxType2BaseTax[taxType][i]
       

    def _checkValidity(self, traRepTaxReps):
        if not isinstance(traRepTaxReps, list):
            raise TypeError("traRepTaxReps must be a list of TradeRepublicTaxReport instances")
        
        if len(traRepTaxReps) == 0 or 2 < len(traRepTaxReps):
            raise TypeError("traRepTaxReps must have a length in [0;2]")

        for rep in traRepTaxReps:
            if not isinstance(rep, TradeRepublicTaxReport):
                raise TypeError("All elements in traRepTaxReps must be instances of TradeRepublicTaxReport")
            
        if len(traRepTaxReps) == 2:
            if traRepTaxReps[0].year * 100 + traRepTaxReps[0].month > traRepTaxReps[1].year * 100 + traRepTaxReps[1].month:
                tmp = traRepTaxReps[0]
                traRepTaxReps[0] = traRepTaxReps[1]
                traRepTaxReps[1] = tmp 
            firstRep = traRepTaxReps[0]
            secRep = traRepTaxReps[1]
            if (firstRep.year, firstRep.month + 1) != (secRep.year, secRep.month) and (firstRep.year + 1, 1) != (secRep.year, secRep.month):
                raise TypeError("traRepTaxReps must be a list of 2 consecutive TradeRepublicTaxReport instances")
            
    def generateTOBReportPDF(self):
        reportName = str(self.traRepTaxReps[0].year) + str(self.traRepTaxReps[0].month)
        if len(self.traRepTaxReps) == 2:
            reportName += "_" + str(self.traRepTaxReps[1].year) + str(self.traRepTaxReps[1].month)
        reportName += "_" + "TOB.pdf"
        shutil.copy(TOB_FILEPATH, reportName)

        reader = PdfReader(reportName)
        writer = PdfWriter()

        for pageNum in range(len(reader.pages)):
            page = reader.pages[pageNum]
            buffer = BytesIO()
            canvas = Canvas(buffer)


            if pageNum == 0:

                def writePeriod():
                    firstRep = self.traRepTaxReps[0]
                    secRep = self.traRepTaxReps[1] if len(self.traRepTaxReps) == 2 else None
                    firstRepMonthX, firstRepMonthY = 286, 690
                    secRepMonthX, secRepMonthY = 388, 690
                    canvas.drawString(firstRepMonthX, firstRepMonthY, str(firstRep.month) + " " + str(firstRep.year)[2:])
                    if secRep:
                        canvas.drawString(secRepMonthX, secRepMonthY, str(secRep.month) + " " + str(secRep.year)[2:])

                def writeId():
                    nnX, nnY = 300, 585
                    nameX, nameY = 300, 572
                    adrX, adrY = 300, 550
                    canvas.drawString(nnX, nnY, self.NN)
                    canvas.drawString(nameX, nameY, self.lastName + " " + self.firstName)
                    canvas.drawString(adrX, adrY, self.address)

                def writeBaseTax():
                    baseX, taxX = 395, 525
                    lowY, midY, highY = 480, 456, 432 
                    def drawBaseTax(y, taxType):
                        baseTax = self.taxType2BaseTax[taxType]
                        if baseTax != [0.0, 0.0]:
                            base = "{:.2f}".format(baseTax[0]).replace(".", ",")
                            tax = "{:.2f}".format(baseTax[1]).replace(".", ",")
                            canvas.drawString(baseX - canvas.stringWidth(base, "Helvetica", 12), y, base)
                            canvas.drawString(taxX - canvas.stringWidth(tax, "Helvetica", 12), y, tax)
                    drawBaseTax(lowY, TaxType.LOW)
                    drawBaseTax(midY, TaxType.MID)
                    drawBaseTax(highY, TaxType.HIGH)
                
                writePeriod()
                writeId()
                writeBaseTax()
            
            elif pageNum == 1:
                def writeTotalTax():
                    totalX, totalY = 445, 450
                    totalTax = "{:.2f}".format(self.totalTax).replace(".", ",")
                    canvas.drawString(totalX - canvas.stringWidth(totalTax, "Helvetica", 12), totalY, totalTax)

                def writeSignature():
                    sigTextX, sigTextY = 90, 310
                    nameX, nameY = 230, 260
                    sigX, sigY = 90, 265
                    signature = SIGN_ADDRESS + ", le " + datetime.datetime.today().strftime('%d/%m/%Y')
                    canvas.drawString(nameX, nameY, self.lastName + " " + self.firstName)
                    canvas.drawString(sigTextX, sigTextY, signature)

                    sigImg = Image.open(SIGNATURE_FILEPATH)
                    sigBuffer = BytesIO()
                    sigImg.save(sigBuffer, format='PNG')

                    sigTmpPath = "sigTmp.png"
                    with open(sigTmpPath, "wb") as tmpFile:
                        tmpFile.write(sigBuffer.getvalue())

                    sigBuffer.seek(0)
                    canvas.drawImage(sigTmpPath, sigX, sigY, 100, 30)
                    os.remove(sigTmpPath)


                writeTotalTax()
                writeSignature()
            
            else:
                writer.add_page(page)
                continue

            canvas.save()
            buffer.seek(0)
            overlay = PdfReader(buffer)
            page.merge_page(overlay.pages[0])
            writer.add_page(page)

        with open(reportName, 'wb') as output_file:
            writer.write(output_file)
            print(reportName + " created")
            output_file.close()

    def generateQRcode(self):
        firstRep = self.traRepTaxReps[0]
        secRep = self.traRepTaxReps[1] if len(self.traRepTaxReps) == 2 else None
        period = "{} {}".format(firstRep.month,firstRep.year)
        if secRep:
           period += " et {} {}".format(secRep.month,secRep.year)
        paiement = consumer_epc_qr(
            beneficiary= BENEFICIARY,
            iban= IBAN,
            amount= self.totalTax,
            remittance= "TOB periode" + period + " numéro national " + self.NN
            )
        paiement.to_qr()
