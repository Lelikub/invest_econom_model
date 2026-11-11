from pathlib import Path
import argparse

class ApplicationInterface:
    def run(self,argv=None) -> int:
        from .models import PipelineConfig
        app=Path(__file__).resolve().parents[1]; repo=app.parents[1]
        parser=argparse.ArgumentParser(description='Практическая 4 ФИП: единый проверяемый pipeline')
        parser.add_argument('--pdf',type=Path)
        parser.add_argument('--lecture',type=Path)
        parser.add_argument('--template',type=Path,help='Шаблон итогового DOCX; по умолчанию контрольная копия или шаблон из lectuion')
        parser.add_argument('--output',type=Path,default=app/'output')
        parser.add_argument('--excel-timeout',type=int,default=90)
        args=parser.parse_args(argv)
        output=args.output.resolve()
        if not output.is_relative_to(app) or output==app or output.parts[len(app.parts):len(app.parts)+1] in [('data',),('src',),('tests',),('docs',),('logs',),('.venv',)]:
            print('FAILED: output must be a dedicated directory inside 4/app'); return 1
        # Default root keeps shared service artifacts and reports coherent.
        if output!=app/'output':
            print('FAILED: this implementation supports only 4/app/output as output directory'); return 1
        pdf=args.pdf or (app/'data/source_assignment.pdf' if (app/'data/source_assignment.pdf').is_file() else next((app.parent/'data').glob('*.pdf'),app/'data/source_assignment.pdf'))
        lecture=args.lecture or (app/'data/source_lecture7.pdf' if (app/'data/source_lecture7.pdf').is_file() else next((repo/'lectuion').glob('*7*.pdf'),app/'data/source_lecture7.pdf'))
        from .controller import PipelineController
        return PipelineController().run(PipelineConfig(app,pdf.resolve(),lecture.resolve(),output,args.excel_timeout,args.template.resolve() if args.template else None))
