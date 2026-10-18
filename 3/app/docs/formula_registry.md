# Реестр формул

Все ставки — доли единицы/год (USD), beta/рычаг/DSCR — безразмерные; деньги — млн USD. Каждый идентификатор соответствует строке таблиц и Excel; калькуляторы не читают файлы. Python ↔ независимые формулы Excel: rtol=1e-8, atol=1e-10. Округлённый DSCR источника: отдельный абсолютный допуск 0.0002x.

| ID | Этап / PDF | Лекция 5 | Формула / входы | Калькулятор | Независимая проверка / выход / отчёт |
|---|---|---|---|---|---|
| t_eff | 1 / 5–6 | 29 | max(t_nominal-rd_relief,t_floor) | EffectiveTaxCalculator | Excel MAX / base_metrics.csv / §6 |
| de_peer | 1 / 5–6 | 15 | debt_peer/equity_peer | LeverageCalculator | Excel / base_metrics.csv / §6 |
| beta_u | 1 / 6 | 15 | beta_peer/(1+(1-tax_peer)*de_peer) | HamadaBetaCalculator | Excel / base_metrics.csv / §6 |
| de | 1 / 6 | 15 | wd/we | LeverageCalculator | Excel / base_metrics.csv / §6 |
| beta_l | 1 / 6 | 15 | beta_u*(1+(1-t_eff)*de) | HamadaBetaCalculator | Excel / base_metrics.csv / §6 |
| ke | 1 / 6 | 19 | rf+beta_l*erp+crp | CAPMCalculator | Excel / base_metrics.csv / §6 |
| kd | 1 / 6 | 6 | rf+s_base | CostOfDebtCalculator | Excel / base_metrics.csv / §6 |
| kd_after_tax | 1 / 6 | 6 | kd*(1-t_eff) | CostOfDebtCalculator | Excel / base_metrics.csv / §6 |
| wacc | 1 / 6 | 17 | we*ke+wd*kd_after_tax | WACCCalculator | Excel / base_metrics.csv / §6 |
| returns | 2 / 6–7 | 18 | P_t/P_(t-1)-1, последняя цена полного месяца | MonthlyReturnsCalculator | Проверка общих дат / monthly_returns.csv / §7 |
| beta_ols,alpha_raw,r_squared,p_value,stderr | 2 / 7 | 18 | linregress(R_market,R_HXL); R²=r² | OLSRegressionCalculator | Синтетическая прямая + Excel SLOPE/INTERCEPT/RSQ / ols_summary.csv / §7 |
| beta_difference | 2 / 7 | 18 | beta_ols-beta_peer; относительное /abs(beta_peer) | MetricService | Разность таблиц / beta_comparison.csv / §7 |
| alpha_jensen | 2 / 7 | — | excess returns требуют временного ряда Rf | OLSRegressionCalculator | NOT_CALCULATED: ряд не предоставлен / ols_summary.csv / §7 |
| edge_beta,edge_equity,edge_tax | 3 / 7–8 | 6,15,17,19 | beta=0 → Ke=Rf+CRP; D=0 → beta_L=beta_U,WACC=Ke; t=0 → Kd_net=Kd | соответствующие калькуляторы | Аналитические тождества / test_results.csv / §8 |
| pi_exp | 4 / 8 | 23,26 | eta*oil | StressShocksCalculator | Excel / stress_metrics.csv / §9 |
| rf | 4 / 8 | 26 (уточнено PDF) | rf0+pi_exp+term_premium+alpha_cross*taiwan | StressShocksCalculator | Excel / stress_metrics.csv / §9 |
| beta_u | 4 / 8 | 28 (уточнено PDF) | beta_u0*(1+psi_tariff*tariff+psi_energy*oil+psi_cross*tariff*oil+psi_tw*taiwan) | StressShocksCalculator | Excel + изолированные шоки / stress_metrics.csv / §9 |
| delta_total | 4 / 8 | 27 (уточнено PDF) | crash+flight | StressShocksCalculator | Excel / stress_metrics.csv / §9 |
| equity,debt,de,we,wd | 4 / 9 | 27 | E0=we0*CAPEX,D0=wd0*CAPEX; E=E0*(1-delta_total),D=D0; de=D/E; we=E/(E+D),wd=D/(E+D) | LeverageCalculator | Excel + we+wd=1 / comparison.csv / §9; CAPEX — масштаб условной начальной стоимости |
| beta_l | 4 / 9 | 29 | beta_u*(1+(1-t_eff)*de) | HamadaBetaCalculator | Excel / stress_metrics.csv / §9 |
| erp | 4 / 9 | 29 | erp0+panic_lambda*crash (НЕ delta_total) | StressShocksCalculator | Excel / stress_metrics.csv / §9 |
| crp | 4 / 9 | 19,29 | crp0+crp_europe+taiwan; CRP_Taiwan=GPR_Taiwan — раскрытое отображение | StressShocksCalculator | Excel / stress_metrics.csv / §9 |
| ke | 4 / 9 | 29 | rf+beta_l*erp+crp | CAPMCalculator | Excel / stress_metrics.csv / §9 |
| dscr | 4 / 9 | 30 (уточнено PDF) | dscr0*(1-mu_ebitda) | DSCRCalculator | Excel / stress_metrics.csv / §9 |
| credit_spread | 4 / 9 | 30 | 0 при dscr>=c; gamma1*(c/dscr-1) при 1<=dscr<c; gamma2*default_spread+penalty при dscr<1 (BLOCKED без входов) | CreditSpreadCalculator | Excel IF + тесты границ / stress_metrics.csv / §9 |
| kd,kd_after_tax,wacc | 4 / 9–10 | 6,26 | kd=rf+s_base+spread_europe+credit_spread; kd_net=kd*(1-t_eff); wacc=we*ke+wd*kd_net | отдельные калькуляторы | Excel / stress_metrics.csv / §9 |
| wacc_decomposition | 4 / 10 | 26 | we0*(Ke1-Ke0); wd0*(Kdnet1-Kdnet0); (we1-we0)*Ke1+(wd1-wd0)*Kdnet1 | MetricService | Сумма = WACC1-WACC0 / wacc_decomposition.csv / §9; порядок фиксирован, не причинная атрибуция |
| ebitda,lockup | 5 / 10–11 | 30 | ebitda0*(1-mu); dscr<c | DSCRCalculator,CovenantService | Excel / waterfall.csv / §10 |
| cfads_before_debt_service,cash_after_debt_service | 5 / 11 | 30 | EBITDA-Taxes-dNWC; CFADS_before-DebtService | CashWaterfallCalculator | Excel / waterfall_summary.csv / §10; налоги,dNWC неизвестны |
| waterfall | 5 / 11 | — | Revenue-OPEX-Taxes-DebtService-DSRA-Dividends=Retained | CashWaterfallCalculator | Баланс + Excel / waterfall.csv / §10; иллюстрация Taxes=0,dNWC=0,Revenue=150,OPEX=Revenue-EBITDAcrisis,DSRA=max(0,cash_after) при lockup |
| literal_waterfall | 5 / 11 | — | Только буквальная демонстрация: lockup → DebtService=0 | CashWaterfallCalculator | Отдельная таблица, не основная экономика / waterfall_literal.csv / §10 |
| discount_factor | Резюме / 12 | 17 | 1/(1+wacc)^t, t=1..10, единичный будущий поток | DiscountEffectCalculator | Excel / discount_factors.csv / §14 |

Неизвестные налоговые платежи, DSRA-политика и NWC не определяются ставкой t_eff. Налоговый щит цены долга не равен денежному налогу. NPV/IRR и типовая доходность отрасли без исходного источника не рассчитываются.
