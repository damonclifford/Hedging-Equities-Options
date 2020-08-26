from QuantConnect.Data.UniverseSelection import * 
from Selection.FundamentalUniverseSelectionModel import FundamentalUniverseSelectionModel 
from QuantConnect.Data.Custom.SEC import *
from Selection.OptionUniverseSelectionModel import OptionUniverseSelectionModel

from datetime import timedelta, datetime
from math import ceil
from itertools import chain
import numpy as np
#imports necessary packages

class universe(FundamentalUniverseSelectionModel):

    def __init__(self, numCoarse = 2500, numFine = 250, numPortfolio = 5, 
                 debttoequityMaxAllowance =  0.8, bound = 0.2, minContractExpiry = 30,
                 maxContractExpiry = 60, filterFineData = True, universeSettings = None, securityInitializer = None):
        super().__init__(filterFineData, universeSettings, securityInitializer)

        # Number of stocks in Coarse Universe
        self.NumberOfSymbolsCoarse = numCoarse
        # Number of sorted stocks in the fine selection subset using the valuation ratio, EV to EBITDA (EV/EBITDA)
        self.NumberOfSymbolsFine =  numFine
        # Final number of stocks in security list, after sorted by the valuation ratio, Return on Assets (ROA)
        self.NumberOfSymbolsInPortfolio = numPortfolio
       
        self.debttoequityMaxAllowance = debttoequityMaxAllowance
        self.bound = bound
        self.minContractExpiry = minContractExpiry
        self.maxContractExpiry = maxContractExpiry
       
        self.lastmonth = -1
        self.dollarVolumeBySymbol = {}
        

    def SelectCoarse(self, algorithm, coarse):
      
        month= algorithm.Time.month
        if month == self.lastmonth:
            return Universe.Unchanged
        self.lastmonth= month
        #We only want to run universe selection once a month

        # sort the stocks by dollar volume and take the top 2000
        top = sorted([x for x in coarse if x.HasFundamentalData],
                    key=lambda x: x.DollarVolume, reverse=True)[:self.NumberOfSymbolsCoarse]
        
        #assigns all the stocks from price to dollarVolumeBySymbol
        self.dollarVolumeBySymbol = { i.Symbol: i.DollarVolume for i in top }

        return list(self.dollarVolumeBySymbol.keys())
    

    def SelectFine(self, algorithm, fine):
        self.priceAllowance = 30

        # QC500:
        ## The company's headquarter must in the U.S. 
        ## The stock must be traded on either the NYSE or NASDAQ 
        ## At least half a year since its initial public offering 
        ## The stock's market cap must be greater than 500 million 
        ## We want the stock's debt to equity ratio to be relatively low to enssure we are investing in stable companies
    
        filteredFine = [x for x in fine if x.CompanyReference.CountryId == "USA"
                                        and x.Price > self.priceAllowance
                                        and (x.CompanyReference.PrimaryExchangeID == "NYS" or x.CompanyReference.PrimaryExchangeID == "NAS")
                                        and (algorithm.Time - x.SecurityReference.IPODate).days > 180
                                        and (x.EarningReports.BasicAverageShares.ThreeMonths * x.EarningReports.BasicEPS.TwelveMonths * x.ValuationRatios.PERatio > 5e8)
                                        and 0 <= (x.OperationRatios.TotalDebtEquityRatioGrowth.OneYear) <= self.debttoequityMaxAllowance #this value will change in accordance to S&P Momentum
                                        and x.FinancialStatements.BalanceSheet.AllowanceForDoubtfulAccountsReceivable.ThreeMonths <= 2.0 * x.FinancialStatements.CashFlowStatement.ProvisionandWriteOffofAssets.ThreeMonths
                                        and (x.FinancialStatements.IncomeStatement.ProvisionForDoubtfulAccounts.TwoMonths <= 1.0*x.FinancialStatements.CashFlowStatement.ProvisionandWriteOffofAssets.ThreeMonths)
                
                                    ]
       
            
      
        count = len(filteredFine)
        if count == 0: return []

        myDict = dict()
        percent = self.NumberOfSymbolsFine / count

        # select stocks with top dollar volume in every single sector based on specific sector ratios
        # N=Normal (Manufacturing), M=Mining, U=Utility, T=Transportation, B=Bank, I=Insurance
        
        
        for key in ["N", "M", "U", "T", "B", "I"]:
            value1 = [x for x in filteredFine if x.CompanyReference.IndustryTemplateCode == key]
            value2 = []
            
            #We use an if/elif statement here to speed up the code runtime
            if key == "N":
                
                value2 = [i for i in value1 if (1.0 <= i.OperationRatios.InventoryTurnover.ThreeMonths <= 2.0)]
                
            elif key == "M":
                
                value2 = [i for i in value1 if i.OperationRatios.QuickRatio.ThreeMonths >= 1.0]
                
            elif key == "U":
                
                value2 = [i for i in value1 if i.OperationRatios.InterestCoverage.ThreeMonths >= 2.0]
                
            elif key == "T":
                
                value2 = [i for i in value1 if i.OperationRatios.ROA.ThreeMonths >= 0.04]
            
            elif key == "B":
                
                value2 = [i for i in value1 if (i.FinancialStatements.IncomeStatement.OtherNonInterestExpense.ThreeMonths / i.FinancialStatements.IncomeStatement.TotalRevenue.ThreeMonths) < 0.60]
            
            else:
                
                value2 = [i for i in value1 if i.OperationRatios.LossRatio.ThreeMonths < 1.0]
                
            value3 = sorted(value2, key=lambda x: self.dollarVolumeBySymbol[x.Symbol], reverse = True)
            myDict[key] = value3[:ceil(len(value3) * percent)]

        # stocks in QC500 universe
        topFine = chain.from_iterable(myDict.values())

        # sort stocks in the security universe of QC500 based on Enterprise Value to EBITDA valuation ratio
        sortedByEVToEBITDA = sorted(topFine, key=lambda x: x.ValuationRatios.EVToEBITDA , reverse=True)

        # sort subset of stocks that have been sorted by Enterprise Value to EBITDA, based on the valuation ratio Return on Assets (ROA)
        sortedByROA = sorted(sortedByEVToEBITDA[:self.NumberOfSymbolsFine], key=lambda x: x.ValuationRatios.ForwardROA, reverse=False)

        # retrieve list of securites in portfolio
        self.stocks = sortedByROA[:self.NumberOfSymbolsInPortfolio]
        
        self.contract = [self.GetContract(algorithm, stock) for stock in self.stocks]
        #This block is different than original options code, much easier than what the original structure was 

        #Following block of code combines both the symbols of equities and options
        res = [i for i in self.contract if i] 
        self.result=[]
        for t in res: 
            for x in t: 
                self.result.append(x)
        self.newstocks= [x.Symbol for x in self.stocks]
        
        #Returns our equities and hedged options
        return [x for x in self.newstocks + self.result]

    
    def GetContract(self, algorithm, stock):
        #unlike Options code we pass in the stock each time we call the GetContract function
        
        #set target strike 20% away
        #these lines are different to, calls built in method of price for each corresponding stock 
        lowertargetStrike = (stock.Price * (1-self.bound)) 
        uppertargetStrike=(stock.Price * (1+self.bound)) 
   
        #pulls contract data for select equity at current time
        contracts=algorithm.OptionChainProvider.GetOptionContractList(stock.Symbol, algorithm.Time)
   
        #selects the type of option to be Put contract
        #then selects all contracts that meet our expiration criteria
        #We want between 30 and 60 days as we do not want to hold our options close to expiration
        
        #Can do all filtering in one line for redundancy (both puts and calls)
        #Leads to less looping and sorting
        puts = [x for x in contracts if x.ID.OptionRight == OptionRight.Put and \
                                        x.ID.StrikePrice < lowertargetStrike and \
                                       self.minContractExpiry < (x.ID.Date - algorithm.Time).days <= self.maxContractExpiry]
        if not puts:
            return
        
        #sorts contracts by closet expiring date date and closest strike price (sorts in ascending order)
        puts = sorted(sorted(puts, key = lambda x: x.ID.Date), 
            key = lambda x: x.ID.StrikePrice)
        
        #selects the type of option to be Put contract
        #then selects all contracts that meet our expiration criteria
        call = [x for x in contracts if x.ID.OptionRight ==OptionRight.Call and \
                                        x.ID.StrikePrice > uppertargetStrike and \
                                        self.minContractExpiry < (x.ID.Date - algorithm.Time).days <= self.maxContractExpiry]
        if not call:
           return
        
        #sorts contracts by closet expiring date date and closest strike price (sorts in ascending order)
        call = sorted(sorted(call, key = lambda x: x.ID.Date), 
            key = lambda x: x.ID.StrikePrice)
        
        #will eventually return array of optimal puts and calls
        return (puts[0],call[0])