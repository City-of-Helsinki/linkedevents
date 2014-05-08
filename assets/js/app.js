window.apiVersion = 'v0.1';

window.dumpObj = function (obj, name, indent, depth) {
    if (depth > 10) {
        return indent + name + ": max depth reached\n";
    }
    if (typeof obj == "object") {
        var child = null;
        var output = indent + '<b>' + name + ":</b><br>\n";
        indent += "&nbsp;&nbsp;&nbsp;&nbsp;";
        for (var item in obj) {
            try {
                child = obj[item];
            } catch (e) {
                child = "error";
            }
            if (typeof child == "object") {
                output += dumpObj(child, item, indent, depth + 1);
            } else {
                output += indent + '<b>' + item + ":</b> " + child + "<br>\n";
            }
        }
        return output;
    } else {
        return obj;
    }
};

var app = angular.module('simpleClient', ['ui.bootstrap', 'ngCookies', 'ngSanitize'])
    .controller('SimpleClientCtrl', function ($scope, $http, $filter, 
                                              $cookieStore, $modal) {

        $scope.maxSize = 10;
        $scope.queryString = '?include=location,keywords&';
        $scope.currentPage = 1;

        $scope.clear = function () {
            $scope.startDate = null;
            $scope.endDate = null;
        };

        $scope.startDate = $cookieStore.get('startDate');
        $scope.endDate = $cookieStore.get('endDate');

        $scope.formats = ['dd-MMMM-yyyy', 'yyyy/MM/dd', 'shortDate'];
        $scope.format = $scope.formats[0];

        $scope.openStartDate = function ($event) {
            $event.preventDefault();
            $event.stopPropagation();
            $scope.startDateOpened = true;
        };
        $scope.openEndDate = function ($event) {
            $event.preventDefault();
            $event.stopPropagation();
            $scope.endDateOpened = true;
        };

        $scope.search = function () {
            if ($scope.startDate)
                $scope.queryString += 'start=' + $filter('date')($scope.startDate, 'yyyy-MM-dd') + '&';
            if ($scope.startDate)
                $scope. queryString += 'end=' +  $filter('date')($scope.endDate, 'yyyy-MM-dd') + '&';

            $cookieStore.put('startDate', $scope.startDate);
            $cookieStore.put('endDate', $scope.endDate);

            $http({
                method: 'GET',
                url: '/' + window.apiVersion + '/event/' + $scope.queryString
            }).success(function (data) {
                $scope.events = data.results;
                $scope.totalItems = data.count;
                $scope.showPagination = true;
            });

            $scope.currentPage = 1;
        };

        $scope.pageChanged = function () {
            $http({
                method: 'GET',
                url: '/' + window.apiVersion + '/event/' + $scope.queryString + 'page=' + $scope.currentPage
            }).success(function (data) {
                $scope.events = data.results;
            });
        };

        $scope.i18n = function (strObj) {
            var defaultLang = 'fi';

            if (strObj) {
                if (strObj[defaultLang]) {
                    return strObj[defaultLang];
                } else {
                    for (var firstLang in strObj) break;
                    return strObj[firstLang];
                }
            } else {
                return 'undefined';
            }
        };

        $scope.getValues = function (obj) {
            var keys = ['name', 'description']
            var arr = [];
            Object.keys(obj).forEach(function (key) {
                if ($.inArray(key, keys) > 0) {
                    if (obj[key])
                        arr.push(obj[key].toString());
                    else
                        arr.push("");
                }
            });
            console.log(arr);
            return arr;
        };

        $scope.toPrettyList = function (lst) {
            return lst.map(function (item) {
                return $scope.i18n(item.name)
            }).join(', ');
        };

        $scope.openDetails = function (event) {
            $scope.modalInstance = $modal.open({
                templateUrl: 'modal.html',
                controller: 'ModalCtrl',
                resolve: {
                    event: function () {
                        return event;
                    }
                }
            });
        };
    })
    .controller('ModalCtrl', function ($scope, event, $modalInstance) {
            $scope.content = dumpObj(event, "Event", "");

            $scope.close = function () {
                $modalInstance.close();
            };
    });