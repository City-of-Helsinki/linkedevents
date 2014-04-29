window.apiVersion = 'v0.1';

var app = angular.module('simpleClient', ['ui.bootstrap', 'ui.select2'])
    .controller('SimpleClientCtrl', function ($scope, $http, $filter) {

        $scope.clear = function () {
            $scope.startDate = null;
            $scope.endDate = null;
        };

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

        $http({
            method: 'GET',
            url: '/' + window.apiVersion + '/place/'
        }).success(function (data) {
            $scope.places = data.results;
        });

        $http({
            method: 'GET',
            url: '/' + window.apiVersion + '/category/'
        }).success(function (data) {
            $scope.categories = data.results;
        });

        $scope.search = function () {
            var queryString = '?';
            if ($scope.startDate)
                queryString += 'start=' + $filter('date')($scope.startDate, 'yyyy-MM-dd') + '&';
            if ($scope.startDate)
                queryString += 'end=' +  $filter('date')($scope.endDate, 'yyyy-MM-dd') + '&';
            if ($scope.place)
                queryString += 'place=' + $scope.place.id + '&';
            if ($scope.keywords) {
                queryString += 'keywords=' + $scope.keywords.toString() + '&';
            }

            $http({
                method: 'GET',
                url: '/' + window.apiVersion + '/event/' + queryString
            }).success(function (data) {
                $scope.events = data.results;
            });
        }

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
        }

    });
