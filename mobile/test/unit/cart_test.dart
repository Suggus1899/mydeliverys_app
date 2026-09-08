import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:hive/hive.dart';
import 'package:mydeliverys_mobile/features/cart/cart_controller.dart';

void main() {
  late Directory tmp;
  late Box box;

  setUp(() async {
    tmp = await Directory.systemTemp.createTemp('cart_test');
    Hive.init(tmp.path);
    box = await Hive.openBox('cart_box');
  });

  tearDown(() async {
    await box.close();
    await Hive.deleteFromDisk();
    await tmp.delete(recursive: true);
  });

  CartItem item(String product, String restaurant) =>
      CartItem(productId: product, restaurantId: restaurant, name: product);

  group('CartController (RF-CLI-26..29)', () {
    test('persiste inmediatamente en Hive', () {
      final c = CartController(box);
      expect(c.add(item('p1', 'r1'), restaurantName: 'Roma'), CartAddResult.added);
      expect(box.get('active_cart')['items'], hasLength(1));
    });

    test('conflicto mono-restaurante sin confirmedReplace', () {
      final c = CartController(box);
      c.add(item('p1', 'r1'));
      expect(c.add(item('p2', 'r2')), CartAddResult.conflict);
      expect(c.state.count, 1);
    });

    test('confirmedReplace vacia y anade del nuevo restaurante', () {
      final c = CartController(box);
      c.add(item('p1', 'r1'));
      expect(c.add(item('p2', 'r2'), confirmedReplace: true), CartAddResult.added);
      expect(c.state.restaurantId, 'r2');
      expect(c.state.count, 1);
    });

    test('reconstruye tras reinicio en frio', () {
      CartController(box).add(item('p1', 'r1'), restaurantName: 'Roma');
      final reopened = CartController(box);
      expect(reopened.state.count, 1);
      expect(reopened.state.restaurantName, 'Roma');
    });

    test('clear limpia estado y caja', () {
      final c = CartController(box);
      c.add(item('p1', 'r1'));
      c.clear();
      expect(c.state.isEmpty, isTrue);
      expect(box.get('active_cart'), isNull);
    });
  });
}
