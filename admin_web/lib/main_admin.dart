import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'console_app.dart';
import 'core/config/console_kind.dart';

void main() =>
    runApp(const ProviderScope(child: ConsoleApp(kind: ConsoleKind.admin)));
