from openpyxl import Workbook
from .excel import style_book


class HarnessLogWriter:
    HEADERS=['№','Этап','Запрос к ИИ / задача','Сгенерированный или изменённый фрагмент кода',
        'Обнаруженная ошибка / галлюцинация','Причина','Как исправлено','Результат повторной проверки',
        'issue_id','category','run_id','timestamp']

    @classmethod
    def write(cls,path,events):
        wb=Workbook(); ws=wb.active; ws.title='Harness Log'; ws.append(cls.HEADERS)
        latest={event['issue_id']:event for event in events}
        def values(i,event):
            return [i]+[str(event.get(key,''))[:32000] for key in ('stage','task','code','issue','cause','resolution','recheck',
                'issue_id','category','run_id','timestamp')]
        for i,event in enumerate(latest.values(),1): ws.append(values(i,event))
        history=wb.create_sheet('History'); history.append(cls.HEADERS)
        for i,event in enumerate(events,1): history.append(values(i,event))
        if not events: ws.append([0,'Проверка','Наблюдаемых ошибок нет'])
        style_book(wb)
        for sh in wb:
            for col in ('C','D','E','F','G','H'): sh.column_dimensions[col].width=55
            for row in range(2,sh.max_row+1): sh.row_dimensions[row].height=90
        path.parent.mkdir(parents=True,exist_ok=True); wb.save(path)
