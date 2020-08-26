class alpha(AlphaModel):   
    def __init__(self,period = 63,resolution = Resolution.Daily):
      
        self.period = period
        self.resolution = resolution
        self.insightPeriod = Time.Multiply(Extensions.ToTimeSpan(resolution), period)
        self.symbolDataBySymbol ={} 
        self.options = []
        
        resolutionString = Extensions.GetEnumString(resolution, Resolution)
        self.Name = '{}({},{})'.format(self.__class__.__name__, period, resolutionString)
        self.day=None
        
        
    def Update(self, algorithm, data):
   
        insights=[]
        
        if algorithm.Time.day == self.day:
            return []
        #Currently we only want to emit insights once a day
         
        
        for symbol, symbolData in self.symbolDataBySymbol.items():
            
            if not data.Bars.ContainsKey(symbol):
                continue
            
            #Pulls our symbol specific indicators
            #sets the std, ema variables to the current value of the indicators of each of our symbol
            value = algorithm.Securities[symbol].Price
            std=symbolData.STD.Current.Value 
            ema=symbolData.EMA.Current.Value
            putcontract=None
            callcontract=None
            
            for contract in self.options:
                if contract.Underlying.Symbol.Value == symbol.Value:
                    if contract.Right == OptionRight.Put:
                        putcontract = contract
                    if contract.Right == OptionRight.Call:
                        callcontract = contract
                    #Pulls the corresponding call and put contract for each symbol    
                        
                if putcontract is not None and callcontract is not None:
                    break
                  
            #The Alpha strategy longs if equity current price is a standard deviation below EMA and shorts if vice versa
            #Emits flat otherwise
            if value< (ema-std):
                insights.append(Insight.Price(symbol, timedelta(days=1), InsightDirection.Up, 0.0025, 1.00,"Options", .5))
                
                #If we are longing equity and have not already bought a put contract and one exists buy one
                if putcontract is not None and not algorithm.Portfolio[putcontract.Symbol].Invested:
                    algorithm.MarketOrder(putcontract.Symbol,1,True)
                   #If we are trying to buy a put and we already have a call on the equity , we should sell it
                    
                    if callcontract is not None and algorithm.Portfolio[callcontract.Symbol].Invested:
                        algorithm.MarketOrder(callcontract.Symbol,-1,True)
             
                     
            elif value> (ema+std):
                insights.append(Insight.Price(symbol, timedelta(days=1), InsightDirection.Down,0.0025, 1.00,"Options", .5))
                
                #If we are shorting equity and have not already bought a put contract and one exists buy one  
                if callcontract is not None and not algorithm.Portfolio[callcontract.Symbol].Invested:
                    algorithm.MarketOrder(callcontract.Symbol,1,True)
                   
                    #If we are trying to buy a call and we already have a put on the equity , we should sell it
                    if  putcontract is not None and algorithm.Portfolio[putcontract.Symbol].Invested:
                        algorithm.MarketOrder(putcontract.Symbol,-1,True)
            else:
                insights.append(Insight.Price(symbol, timedelta(days=1), InsightDirection.Flat,0.0025, 1.00,"ReversiontotheMean", .5))

        if insights:
            self.day = algorithm.Time.day

        return insights



    def OnSecuritiesChanged(self, algorithm, changes):
        for y in  changes.RemovedSecurities:
            #There are two ways which we can remove options
            
            #1 if an equity is no longer in our universe remove it and corresponding equity
            if y.Symbol.SecurityType ==SecurityType.Equity:
                #can pull all contracts we need to remove through a one-liner
                remove = [contract for contract in self.options if contract.Underlying.Symbol.Value == y.Symbol.Value]
                for x in remove:
                    self.options.remove(x)
                    #As we do not create any indicators with options we do not have any consolidators that we need to remove here
                    
                symbolData = self.symbolDataBySymbol.pop(y.Symbol, None)
                if symbolData:
                    algorithm.SubscriptionManager.RemoveConsolidator(y.Symbol, symbolData.Consolidator)
                    #Remove our consolidators to not slow down our algorithm
            
            #If the option is no longer the desired one and we also arent removing the equity remove it
            elif y.Symbol.SecurityType ==SecurityType.Option:
                if y.Underlying not in [x.Symbol for x in changes.RemovedSecurities]:
                    contractToRemove = [contract for contract in self.options if contract.Symbol == y.Symbol]
                    #Pulls all contracts, both put and call, that we need to remove in above line
                    
                    if len(contractToRemove) > 0:
                        self.options.remove(contractToRemove[0])
                        #If theres actual contracts to remove then do so
                        
                  #As we do not create any indicators with options we do not have any consolidators that we need to remove here

      
        addedSymbols = [ x.Symbol for x in changes.AddedSecurities if (x.Symbol not in self.symbolDataBySymbol and x.Symbol.SecurityType ==SecurityType.Equity)]
     
    
        if len(addedSymbols) == 0: return
        #if no new symbols we do not need to generate any new instances

        for symbol in addedSymbols:
            #can pass all indicators and consolidators through symbol data class
            self.symbolDataBySymbol[symbol] = SymbolData(symbol, algorithm, self.period, self.resolution)
            #Records Symbol Data of each symbol including indicators and consolidator
            
        options = [ x for x in changes.AddedSecurities if (x not in self.options and x.Symbol.SecurityType ==SecurityType.Option)]
        optionSymbols = [x.Symbol for x in options]
        if len(options) == 0: return
    
        # Assign the option underlying
        for option in optionSymbols:
            algorithm.Securities[option].Underlying = algorithm.Securities[option.Underlying] 
       
        newhistory = algorithm.History(optionSymbols, self.period, Resolution.Minute)
    
        if  newhistory.empty: return
        #if no new symbols we do not need to generate any new instances
        
        for contract in options:
            self.options.append(contract)
       #here we do not need an options dictionary can just work with a list where we use the built-in methods later in our update function
  
class SymbolData:
    def __init__(self, symbol, algorithm, period, resolution):
        #Here we can store all the data associated with each symbol including our indicators, consolidators
        #and the history data
        
        self.Symbol = symbol
        
        self.EMA = ExponentialMovingAverage(period)
        self.STD = StandardDeviation(period)
        self.Consolidator = algorithm.ResolveConsolidator(symbol, resolution)
        algorithm.RegisterIndicator(symbol, self.STD, self.Consolidator)
        algorithm.RegisterIndicator(symbol, self.EMA, self.Consolidator)
        #for each new symbol, generate an instance of the indicator std and ema
        
        history = algorithm.History(symbol, period, resolution)
        
        if not history.empty:
            ticker = SymbolCache.GetTicker(symbol)
            #if history isnt empty set the ticker as the symbol
            
            for tuple in history.loc[ticker].itertuples():
                self.EMA.Update(tuple.Index, tuple.close)
                self.STD.Update(tuple.Index, tuple.close)