#include <sys/resource.h>

#include <QApplication>
#include <QTranslator>

#include "system/hardware/hw.h"
#include "selfdrive/ui/qt/qt_window.h"
#include "selfdrive/ui/qt/util.h"
#include "selfdrive/ui/qt/window.h"

int main(int argc, char *argv[]) {
  setpriority(PRIO_PROCESS, 0, -20);

  qInstallMessageHandler(swagLogMessageHandler);
  initApp(argc, argv);

  QApplication a(argc, argv);

  QTranslator translator;
  QString lang =  QString::fromStdString(Params().get("LanguageFile"));
  if(lang.size() > 0) {
    QString path = QString("./translations/%1.qm").arg(lang).trimmed();
    LOGW("Translatoion file: %s", path.toStdString().c_str());

    if(translator.load(path)) {
      if(!a.installTranslator(&translator))
        LOGW("installTranslator failed !!")
    }
    else {
      LOGW("QTranslator load failed !!")
    }
  }

  MainWindow w;
  setMainWindow(&w);
  a.installEventFilter(&w);
  return a.exec();
}
