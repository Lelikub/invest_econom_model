from argparse import ArgumentParser
import sys

from .controller import PipelineController


class ApplicationInterface:
    def __init__(self, app):
        self.app=app

    def run(self):
        parser=ArgumentParser(description="ФИП. Практическая работа № 5")
        parser.add_argument("--skip-excel",action="store_true",help="Сохранить формулы и сверку Python/CBC без запуска Excel")
        parser.add_argument("--skip-editors",action="store_true",help="Проверить структуру документов без Word и PowerPoint")
        args=parser.parse_args()
        if sys.stdout.encoding and sys.stdout.encoding.lower().replace("-","")!="utf8":
            sys.stdout.reconfigure(errors="replace")
        result=PipelineController(self.app).run(not args.skip_excel,not args.skip_editors)
        for event in result["stages"]:
            print(f'{event["stage"]} | {event["status"]} | {event["artifact"]} | {event["detail"]}')
        return 1 if result["status"]=="FAIL" else 0
