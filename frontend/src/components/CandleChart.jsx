import React, { useEffect, useRef, useState } from 'react';
import { createChart, ColorType, CandlestickSeries, LineSeries, createSeriesMarkers } from 'lightweight-charts';

const CandleChart = ({ data, tradePlan, pattern, patternPoints }) => {
    const chartContainerRef = useRef();
    const chartRef = useRef(null);
    const seriesRef = useRef(null);
    const markersPluginRef = useRef(null);
    const linesRef = useRef({ ent: null, tp: null, sl: null });
    const patternSeriesRef = useRef([]);
    const tradePlanRef = useRef(tradePlan);
    const dataSignatureRef = useRef(null); // to detect symbol/timeframe changes
    const [zoneStyles, setZoneStyles] = useState({ risk: { display: 'none' }, reward: { display: 'none' } });

    // Keep tradePlanRef up to date
    useEffect(() => {
        tradePlanRef.current = tradePlan;
    }, [tradePlan]);

    useEffect(() => {
        if (!chartContainerRef.current) return;

        const chart = createChart(chartContainerRef.current, {
            autoSize: true, // Let lightweight-charts handle resizing
            layout: { 
                background: { type: ColorType.Solid, color: 'transparent' }, 
                textColor: '#94a3b8' 
            },
            grid: {
                vertLines: { color: 'rgba(255, 255, 255, 0.05)' },
                horzLines: { color: 'rgba(255, 255, 255, 0.05)' },
            },
            timeScale: {
                timeVisible: true,
                secondsVisible: false,
            },
        });

        const candlestickSeries = chart.addSeries(CandlestickSeries, {
            upColor: '#00ffaa',
            downColor: '#ff4d4d',
            borderVisible: false,
            wickUpColor: '#00ffaa',
            wickDownColor: '#ff4d4d',
            autoscaleInfoProvider: (original) => {
                const res = original();
                if (res !== null && tradePlanRef.current && tradePlanRef.current.entry) {
                    const tp = tradePlanRef.current;
                    const vals = [
                        res.priceRange.minValue,
                        res.priceRange.maxValue,
                        Number(tp.entry),
                        Number(tp.tp),
                        Number(tp.sl)
                    ].filter(v => v !== undefined && v !== null && !isNaN(v));
                    
                    if (vals.length > 0) {
                        const min = Math.min(...vals);
                        const max = Math.max(...vals);
                        const padding = (max - min) * 0.05 || max * 0.01;
                        res.priceRange.minValue = min - padding;
                        res.priceRange.maxValue = max + padding;
                    }
                }
                return res;
            }
        });

        chartRef.current = chart;
        seriesRef.current = candlestickSeries;

        const updateZones = () => {
            if (!chartRef.current || !seriesRef.current || !chartContainerRef.current) return;
            const currentPlan = tradePlanRef.current;
            
            if (!currentPlan || !currentPlan.entry || !currentPlan.tp || !currentPlan.sl) {
                setZoneStyles({ risk: { display: 'none' }, reward: { display: 'none' } });
                return;
            }
            
            const entY = candlestickSeries.priceToCoordinate(currentPlan.entry);
            const tpY = candlestickSeries.priceToCoordinate(currentPlan.tp);
            const slY = candlestickSeries.priceToCoordinate(currentPlan.sl);
            
            if (entY === null || tpY === null || slY === null) {
                setZoneStyles({ risk: { display: 'none' }, reward: { display: 'none' } });
                return;
            }
            
            const width = chartContainerRef.current.clientWidth - 50; 
            if (width <= 0) return;
            
            const startX = width * 0.7; // Start at 70% of the chart width
            const boxWidth = width * 0.3; // Take up 30% of the width
            
            if (currentPlan.tp > currentPlan.entry) {
                // LONG
                setZoneStyles({
                    reward: { display: 'block', top: tpY, height: Math.max(0, entY - tpY), left: startX, width: boxWidth, background: 'linear-gradient(90deg, rgba(0,255,170,0) 0%, rgba(0,255,170,0.15) 100%)', borderTop: '1px dashed rgba(0, 255, 170, 0.6)', borderRight: '2px solid rgba(0, 255, 170, 0.8)' },
                    risk: { display: 'block', top: entY, height: Math.max(0, slY - entY), left: startX, width: boxWidth, background: 'linear-gradient(90deg, rgba(255,77,77,0) 0%, rgba(255,77,77,0.15) 100%)', borderBottom: '1px dashed rgba(255, 77, 77, 0.6)', borderRight: '2px solid rgba(255, 77, 77, 0.8)' }
                });
            } else {
                // SHORT
                setZoneStyles({
                    risk: { display: 'block', top: slY, height: Math.max(0, entY - slY), left: startX, width: boxWidth, background: 'linear-gradient(90deg, rgba(255,77,77,0) 0%, rgba(255,77,77,0.15) 100%)', borderTop: '1px dashed rgba(255, 77, 77, 0.6)', borderRight: '2px solid rgba(255, 77, 77, 0.8)' },
                    reward: { display: 'block', top: entY, height: Math.max(0, tpY - entY), left: startX, width: boxWidth, background: 'linear-gradient(90deg, rgba(0,255,170,0) 0%, rgba(0,255,170,0.15) 100%)', borderBottom: '1px dashed rgba(0, 255, 170, 0.6)', borderRight: '2px solid rgba(0, 255, 170, 0.8)' }
                });
            }
        };

        chart.timeScale().subscribeVisibleTimeRangeChange(updateZones);
        chart.timeScale().subscribeSizeChange(updateZones);

        // Allow external manual zone updates
        chartRef.current.updateZones = updateZones;

        return () => {
            chart.remove();
            chartRef.current = null;
            seriesRef.current = null;
            markersPluginRef.current = null;
        };
    }, []);

    // Handle data updates
    useEffect(() => {
        if (!seriesRef.current || !chartRef.current || !data || data.length === 0) return;
        
        // Make sure data is sorted and has no duplicates by time
        const uniqueData = data.filter((v, i, a) => a.findIndex(t => (t.time === v.time)) === i).sort((a,b) => a.time - b.time);
        
        seriesRef.current.setData(uniqueData);

        // --- Add Markers for Profit Arrow and Pattern Candle ---
        const markers = [];
        if (uniqueData.length >= 2) {
            const lastCandle = uniqueData[uniqueData.length - 1];
            const prevCandle = uniqueData[uniqueData.length - 2];
            
            // 1. Label the candle that influences the market (Pattern)
            if (pattern && pattern !== 'Scanning...' && pattern !== 'Consolidating') {
                const isBullish = pattern.toLowerCase().includes('bullish') || pattern.toLowerCase().includes('hammer') || pattern.toLowerCase().includes('support');
                markers.push({
                    time: prevCandle.time,
                    position: isBullish ? 'belowBar' : 'aboveBar',
                    color: isBullish ? '#00ffaa' : '#ff4d4d',
                    shape: isBullish ? 'arrowUp' : 'arrowDown',
                    text: `✨ ${pattern}`,
                });
            }
            
            // 2. Arrow towards profit direction
            if (tradePlanRef.current && tradePlanRef.current.entry) {
                const tp = tradePlanRef.current.tp;
                const entry = tradePlanRef.current.entry;
                const isLong = tp > entry;
                
                markers.push({
                    time: lastCandle.time,
                    position: isLong ? 'aboveBar' : 'belowBar',
                    color: isLong ? '#00ffaa' : '#ff4d4d',
                    shape: isLong ? 'arrowUp' : 'arrowDown',
                    text: 'PROFIT 🚀',
                });
            }
        }
        // lightweight-charts v5: use createSeriesMarkers() plugin instead of series.setMarkers()
        if (markersPluginRef.current) {
            markersPluginRef.current.setMarkers(markers);
        } else {
            markersPluginRef.current = createSeriesMarkers(seriesRef.current, markers);
        }
        // -----------------------------------------------------------

        // Determine if we should fitContent. We should do this if the data time range jumps drastically (e.g. symbol switch).
        const currentFirstTime = uniqueData[0].time;
        if (!dataSignatureRef.current || Math.abs(dataSignatureRef.current - currentFirstTime) > 86400 * 2) {
            chartRef.current.timeScale().fitContent();
        }
        dataSignatureRef.current = currentFirstTime;

        if (chartRef.current.updateZones) {
            chartRef.current.updateZones();
        }
    }, [data]);

    // Handle trade plan updates (lines)
    useEffect(() => {
        if (!seriesRef.current || !chartRef.current) return;

        // Remove old lines
        if (linesRef.current.ent) seriesRef.current.removePriceLine(linesRef.current.ent);
        if (linesRef.current.tp) seriesRef.current.removePriceLine(linesRef.current.tp);
        if (linesRef.current.sl) seriesRef.current.removePriceLine(linesRef.current.sl);
        linesRef.current = { ent: null, tp: null, sl: null };

        if (tradePlan && tradePlan.entry && tradePlan.tp && tradePlan.sl) {
            linesRef.current.ent = seriesRef.current.createPriceLine({
                price: tradePlan.entry, color: '#ffffff', lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: 'ENT',
            });
            linesRef.current.tp = seriesRef.current.createPriceLine({
                price: tradePlan.tp, color: '#00ffaa', lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: 'TP',
            });
            linesRef.current.sl = seriesRef.current.createPriceLine({
                price: tradePlan.sl, color: '#ff4d4d', lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: 'SL',
            });

            setTimeout(() => {
                if (chartRef.current && chartRef.current.updateZones) {
                    chartRef.current.updateZones();
                }
            }, 50);
        } else {
            setZoneStyles({ risk: { display: 'none' }, reward: { display: 'none' } });
        }
    }, [tradePlan]);

    // Draw Pattern Lines
    useEffect(() => {
        if (!chartRef.current) return;

        // Clean up previous lines
        patternSeriesRef.current.forEach(series => {
            try {
                chartRef.current.removeSeries(series);
            } catch(e) {}
        });
        patternSeriesRef.current = [];

        if (Array.isArray(patternPoints) && patternPoints.length > 0) {
            patternPoints.forEach(lineData => {
                const lineSeries = chartRef.current.addSeries(LineSeries, {
                    color: 'rgba(0, 212, 255, 0.3)', // Reduced opacity for blue lines
                    lineWidth: 1, // Thinner lines
                    lineStyle: 2, // Dashed lines
                    crosshairMarkerVisible: false,
                    priceLineVisible: false,
                    lastValueVisible: false,
                });
                
                try {
                    lineSeries.setData(lineData);
                    patternSeriesRef.current.push(lineSeries);
                } catch(e) {
                    console.error("Error drawing pattern line:", e);
                }
            });
        }
    }, [patternPoints]);

    return (
        <div style={{ position: 'relative', width: '100%', height: '350px' }}>
            {tradePlan?.entry && (
                <>
                    <div style={{ position: 'absolute', pointerEvents: 'none', zIndex: 1, ...zoneStyles.risk }}>
                        <span style={{ position: 'absolute', right: '10px', top: '5px', fontSize: '10px', color: '#ff4d4d' }}>Risk Area</span>
                    </div>
                    <div style={{ position: 'absolute', pointerEvents: 'none', zIndex: 1, ...zoneStyles.reward }}>
                        <span style={{ position: 'absolute', right: '10px', bottom: '5px', fontSize: '10px', color: '#00ffaa' }}>Reward Area</span>
                    </div>
                </>
            )}
            <div ref={chartContainerRef} style={{ position: 'relative', zIndex: 2, width: '100%', height: '100%' }} />
        </div>
    );
};

export default CandleChart;
